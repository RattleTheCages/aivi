#   AIQuickKeyEditor    -- The editor that wrote itself.
#AIQuickKeyEditor is the prototype editor for the Aivi editor.
#This editor is a fully functioning editor that offers AI assistance.
#The top window is where you enter text and edit it; the bottom window is the AI command window, where you can enter requests for AI assistance.
#Use ctrl-v to choose the type of AI assistance you need, such as grammar and spelling corrections, or Python coding.
#In freestyle mode, one can enter any question or content, similar to a well-known subscription AI interface.
#This work is copyright. All rights reserved.

import os
import json
import argparse
import curses
import signal
from openai import OpenAI

parser = argparse.ArgumentParser()
parser.add_argument('file', nargs='?', default=None)
args = parser.parse_args()
client = OpenAI(api_key=os.environ.get("CUSTOM_ENV_NAME"))

class CogQuery:
    @classmethod
    def get_unique_request_counter(cls, file_base_name):
        while os.path.exists(f'{file_base_name}_{cls.request_counter}.txt'):
            cls.update_request_counter()
        return cls.request_counter
    request_counter = 0
    def __init__(self, role, content):
        self.role = role
        self.content = content
    @classmethod
    def update_request_counter(cls):
        cls.request_counter += 1
        return cls.request_counter
    @classmethod
    def reset_request_counter(cls):
        cls.request_counter = 0

class Cognalities:
    def __init__(self):
        self.cognalities = {
            'Spelling': {
                'attributes': [
                    'Your only task correct mispelled words.',
                    'Answer strictly only using the correctly spelled words, do not change punctuation or sentence structure.',
                    'Take each sentence and output a corresponding corrected sentence.',
                    'The user wants the answer strictly formatted as the question.'
                ],
                'model': 'gpt-3.5-turbo',
                'max_tokens': 298,
                'flags': {'concatenate': False, 'replace': True}
            },
            'Python Coder': {
                'attributes': [
                    'Your task is to code in python.',
                    'You are one of the best programmers who will think of every task to complete.',
                    'You are very competent and good at writing code.',
                    'Besure to write the entire function when there are any modification to that function.',
                    'When the code is longer than 222 lines, only write the modified functions; ',
                    'and indent the modified functions so they can be yanked and pasted into the code.'
                ],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                'flags': {'concatenate': True, 'replace': False}
            },
            'Spelling and Grammar': {
                'attributes': [
                    'Your task is to spell and grammar check the given sentences.'
                    #'If needed, rewrite the sentences at a higher education level.'
                ],
                'model': 'gpt-4',
                'max_tokens': 698,
                'flags': {'concatenate': False, 'replace': True}
            },
            'Freestyle': {
                'attributes': [],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                'flags': {'concatenate': True, 'replace': False}
            },
            'Telephone': {
                'attributes': [
                    "This is the children's game of 'telephone', play nicely."
                ],
                'model': 'gpt-4',
                'max_tokens': 698,
                'flags': {'concatenate': True, 'replace': False}
            }
        }
        self.names = list(self.cognalities.keys())
        self.current_index = 0
    def get_current_name(self):
        return self.names[self.current_index]
    def get_attributes(self):
        return self.cognalities[self.get_current_name()]['attributes']
    def next_cognality(self):
        self.current_index = 0
    def get_current_name(self):
        return self.names[self.current_index]
    def get_attributes(self):
        return self.cognalities[self.get_current_name()]['attributes']
    def next_cognality(self):
        self.current_index = (self.current_index + 1) % len(self.names)
        return self.get_current_name()
    def get_attributes_by_name(self, name):
        return self.cognalities.get(name, {}).get('attributes', [])
    def get_model(self):
        return self.cognalities[self.get_current_name()]['model']
    def get_maxtokens(self):
        return self.cognalities[self.get_current_name()]['max_tokens']
    def get_flags(self):
        return self.cognalities[self.get_current_name()]['flags']

class Cogtext:
    def __init__(self, cognalities):
        self.cognalities = cognalities
        self.cogessages = []
        self.usermsg = []
    def reset(self):
        self.cogessages = []
        self.usermsg = []
    def add_cogtext(self, role, content):
        self.cogessages.append(CogQuery(role, content))
    def add_cogatt(self, name, role, content):
        if name in self.cognalities.cognalities:
            self.cogessages.append(CogQuery(role, content))
    def get_cogtext(self):
        context = [{"role": message.role, "content": message.content} for message in self.cogessages]
        context += [{"role": "user", "content": umsg} for umsg in self.usermsg]
        return context
    def get_cogtext_by_name(self, name):
        attributes = self.cognalities.get_attributes_by_name(name)
        context = [{"role": "system", "content": attribute} for attribute in attributes]
        context += [{"role": "user", "content": umsg} for umsg in self.usermsg]
        return context
    def add_usermsg(self, msg):
        self.usermsg.append(msg)
    def save_cogtext(self, filename):
        with open(filename, 'w') as f:
            json.dump({
                "model": self.cognalities.get_model(),
                "max_tokens": self.cognalities.get_maxtokens(),
                "messages": self.get_cogtext()
            }, f)
    def load_cogtext(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                self.cognalities.model = data.get('model', '')
                self.cognalities.max_tokens = data.get('max_tokens', 0)
                self.cogessages = [CogQuery(item['role'], item['content']) for item in data.get('messages', [])]

class AIQuickKeyEditor:
    def __init__(self, stdscr):
        signal.signal(signal.SIGINT, self.handle_sigint)
        self.stdscr = stdscr
        self.mode = 'line'
        self.status = 'hello'
        self.clipboard = []
        self.yanked_lines = set()
        self.yank_mode_active = False
        self.context_window = 0
        self.search_results = []
        self.current_search_result = -1
        self.windows = [
            {"line_num": 0, "col_num": 0, "text": [""]},
            {"line_num": 0, "col_num": 0, "text": [""]},
        ]
        self.window_offsets = [0, 0]
        self.cognalities = Cognalities()
        self.personalchoice = self.cognalities.get_current_name()
        self.context = Cogtext(self.cognalities)
        self.filename = args.file if args.file else 'quickAi.txt'
        if os.path.exists(self.filename):
            self.read_file()
        else:
            self.show_splash_screen()
    def handle_return(self):
        current_window = self.windows[self.context_window]
        line = current_window["text"][current_window["line_num"]]
        self.context.add_cogtext("user", line)
        self.context.add_usermsg(line)
        current_window["text"].insert(current_window["line_num"] + 1, current_window["text"][current_window["line_num"]][current_window["col_num"]:])
        current_window["text"][current_window["line_num"]] = current_window["text"][current_window["line_num"]][:current_window["col_num"]]
        current_window["line_num"] += 1
        current_window["col_num"] = 0
        self.adjust_window_offset()
    def display(self):
        modeOrStatus = self.mode
        if self.status != "":
            modeOrStatus = self.status
            self.status = ""
        top_window = self.windows[0]["text"]
        bottom_window = self.windows[1]["text"]
        self.stdscr.clear()
        for y in range(min(38, len(top_window) - self.window_offsets[0])):
            line = top_window[y + self.window_offsets[0]]
            highlight = curses.A_UNDERLINE if self.context_window == 0 and y + self.window_offsets[0] in self.yanked_lines else curses.A_NORMAL
            try:
                self.stdscr.addstr(y, 0, f"{((y + self.window_offsets[0]+1)%1000):03}<{modeOrStatus:5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]) else 0))
                if self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[0]["col_num"]:
                            self.stdscr.addch(ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(ch, curses.A_BOLD)  # add A_BOLD to the whole current line
                    if self.context_window == 0:
                        self.stdscr.move(y, self.windows[0]["col_num"] + len(f"{y + self.window_offsets[0]:03}<{modeOrStatus:5}>"))
                else:
                    self.stdscr.addstr(line)
            except curses.error:
                pass
        for y in range(38, 48):
            if y - 38 >= len(bottom_window) - self.window_offsets[1]:
                break
            highlight = curses.A_UNDERLINE if self.context_window == 1 and y - 38 + self.window_offsets[1] in self.yanked_lines else curses.A_NORMAL
            line = bottom_window[y - 38 + self.window_offsets[1]]
            try:
                self.stdscr.addstr(y, 0, f"{((y - 38 + self.window_offsets[1]+1)%1000):03}<{self.cognalities.get_current_name():5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 1 and y - 38 + self.window_offsets[1] == self.windows[1]["line_num"]) else 0))
                if self.context_window == 1 and y - 38 + self.window_offsets[1] == self.windows[1]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[1]["col_num"]:
                            self.stdscr.addch(ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(ch, curses.A_BOLD)  # add A_BOLD to the whole current line
                    if self.context_window == 1:
                        self.stdscr.move(y, self.windows[1]["col_num"] + len(f"{y - 38 + self.window_offsets[1]:03}<{self.personalchoice:5}>"))
                else:
                    self.stdscr.addstr(line)
            except curses.error:
                pass
        self.stdscr.refresh()
    def adjust_window_offset(self):
        for i in range(2):
            while self.windows[i]["line_num"] < self.window_offsets[i]:
                self.window_offsets[i] -= 1
            while self.windows[i]["line_num"] >= self.window_offsets[i] + (38 if i == 0 else 8):
                self.window_offsets[i] += 1
    def insert_char(self, ch):
        current_window = self.windows[self.context_window]
        line = current_window["text"][current_window["line_num"]]
        if ch in (curses.KEY_BACKSPACE, 127):
            if current_window["col_num"] > 0:
                current_window["text"][current_window["line_num"]] = line[:current_window["col_num"] - 1] + line[current_window["col_num"]:]
                current_window["col_num"] -= 1
            elif current_window["col_num"] == 0 and current_window["line_num"] > 0:
                prev_line = current_window["text"][current_window["line_num"] - 1]
                current_window["col_num"] = len(prev_line)
                current_window["text"][current_window["line_num"] - 1] += current_window["text"].pop(current_window["line_num"])
                current_window["line_num"] -= 1
        elif 0 <= ch <= 0x10FFFF and chr(ch).isprintable():
            self.mode = 'edit'
            current_window["text"][current_window["line_num"]] = line[:current_window["col_num"]] + chr(ch) + line[current_window["col_num"]:]
            current_window["col_num"] += 1
        self.adjust_window_offset()
    def handle_backspace(self, ch):
        if self.mode == 'edit':
            self.insert_char(ch)
        else:
            current_window = self.windows[self.context_window]
            if self.clipboard:
                undo_content = list(current_window["text"])
                current_window["text"].clear()
                current_window["text"].extend(self.clipboard)
                self.clipboard = undo_content
                if self.status == 'undo':
                    self.status = 'redo'
                else:
                    self.status = 'undo'
                if current_window["line_num"] >= len(current_window["text"]):
                    current_window["line_num"] = len(current_window["text"]) - 1
                if current_window["line_num"] < 0:
                    current_window["line_num"] = 0
                if current_window["col_num"] > len(current_window["text"][current_window["line_num"]]):
                    current_window["col_num"] = len(current_window["text"][current_window["line_num"]])
                if current_window["col_num"] < 0:
                    current_window["col_num"] = 0
                self.adjust_window_offset()
    def delete_current_line(self):
        current_window = self.windows[self.context_window]
        if len(current_window["text"]) > 1:
            current_window["text"].pop(current_window["line_num"])
            if current_window["line_num"] >= len(current_window["text"]):
                current_window["line_num"] -= 1
            current_window["col_num"] = 0
        else:
            current_window["text"] = [""]
            current_window["line_num"] = 0
            current_window["col_num"] = 0
        self.adjust_window_offset()
    def handle_up_arrow(self):
        current_window = self.windows[self.context_window]
        if current_window["line_num"] > 0:
            current_window["line_num"] -= 1
            if current_window["col_num"] > len(current_window["text"][current_window["line_num"]]):
                current_window["col_num"] = len(current_window["text"][current_window["line_num"]])
            self.adjust_window_offset()
    def handle_down_arrow(self):
        current_window = self.windows[self.context_window]
        if current_window["line_num"] < len(current_window["text"]) - 1:
            current_window["line_num"] += 1
            if current_window["col_num"] > len(current_window["text"][current_window["line_num"]]):
                current_window["col_num"] = len(current_window["text"][current_window["line_num"]])
            self.adjust_window_offset()
    def handle_right_arrow(self):
        current_window = self.windows[self.context_window]
        line = current_window["text"][current_window["line_num"]]
        if current_window["col_num"] < len(line):
            current_window["col_num"] += 1
        self.status = 'edit'
    def handle_left_arrow(self):
        current_window = self.windows[self.context_window]
        if current_window["col_num"] > 0:
            current_window["col_num"] -= 1
        self.status = 'edit'
    def handle_backslash(self):
        file_base_name = os.path.splitext(self.filename)[0]
        request_id = CogQuery.get_unique_request_counter(file_base_name)
        before_context_filename = f'{file_base_name}_before_context_{request_id}.json'
        ai_context_filename = f'{file_base_name}_ai_context_{request_id}.json'
        self.context.reset()
        chosen_attributes = self.cognalities.get_attributes()
        for attribute in chosen_attributes:
            self.context.add_cogtext("system", attribute)
        if self.context_window == 1:
            userlines = ""
            for line in self.windows[1]["text"]:
                if line.strip():
                    userlines += line + '\n'
            self.context.add_cogtext("user", userlines)
        else:
            userlines = ""
            for line in self.windows[1]["text"]:
                if line.strip():
                    userlines += line + '\n'
            self.context.add_cogtext("system", userlines)
            userlines = ""
            for line in self.windows[0]["text"]:
                if line.strip():
                    userlines += line + '\n'
            self.context.add_cogtext("user", userlines)
        self.context.save_cogtext(before_context_filename)
        self.write_file()
        self.clipboard = [line for line in self.windows[self.context_window]["text"]]
        # I am a fluffy unicorn, with light green spots.
        self.status = 'ai *'
        self.display()
        completion = client.chat.completions.create(
            model=self.cognalities.get_model(),
            max_tokens=self.cognalities.get_maxtokens(),
            messages=self.context.get_cogtext()
        )
        self.context.add_cogtext("assistant", completion.choices[0].message.content)
        self.context.save_cogtext(ai_context_filename)
        flags = self.cognalities.get_flags()
        response_text = completion.choices[0].message.content.split('\n')
        if flags['replace']:
            self.windows[self.context_window]["text"] = response_text
        elif flags['concatenate']:
            self.windows[self.context_window]["text"].extend(response_text)
        self.windows[self.context_window]["line_num"] = len(self.windows[self.context_window]["text"]) - 1
        self.windows[self.context_window]["col_num"] = len(self.windows[self.context_window]["text"][self.windows[self.context_window]["line_num"]])
        self.write_file()
        self.mode = 'reply'
        self.stdscr.nodelay(True)
        try:
            ch = self.stdscr.getch()
            while ch != -1:
                ch = self.stdscr.getch()
        finally:
            self.stdscr.nodelay(False)
        self.adjust_window_offset()
    def write_file(self):
        try:
            file_base_name, file_suffix = os.path.splitext(self.filename)
            # Find unique backup filename for the main file
            while True:
                request_id = CogQuery.update_request_counter()
                backup_filename = f'{file_base_name}.{request_id}{file_suffix}'
                if not os.path.exists(backup_filename):
                    break
            if os.path.exists(self.filename):
                os.rename(self.filename, backup_filename)
            with open(self.filename, 'w+') as f:
                for line in self.windows[0]["text"]:
                    f.write(line + '\n')
            ctx_filename = f'{file_base_name}.ctx'
            # Find unique backup filename for the .ctx file
            while True:
                ctx_rename = f'{file_base_name}.{request_id}.ctx'
                if not os.path.exists(ctx_rename):
                    break
                request_id = CogQuery.update_request_counter()  # update request counter until unique
            if os.path.exists(ctx_filename):
                os.rename(ctx_filename, ctx_rename)
            with open(ctx_filename, 'w+') as f:
                for line in self.windows[1]["text"]:
                    f.write(line + '\n')
                f.write(self.cognalities.get_current_name() + '\n')
            self.status = "wrote"
        except Exception as e:
            self.status = "no wr"
    def read_file(self):
        try:
            with open(self.filename, 'r') as f:
                lines = [line.rstrip('\n') for line in f]
            self.windows[0]["text"] = lines
            self.windows[1]["text"] = [""]
            self.windows[0]["line_num"] = 0
            self.windows[0]["col_num"] = 0
            self.windows[1]["line_num"] = 0
            self.windows[1]["col_num"] = 0
            self.status = "read "
            CogQuery.reset_request_counter()
            self.adjust_window_offset()
        except PermissionError:
            self.status = "denid"
        except IsADirectoryError:
            self.status = "dir  "
        except IOError:
            self.status = "IO er"
        except ValueError as err:
            self.status = "empty"
    def handle_ctrl_x(self):
        if self.yank_mode_active:
            current_window = self.windows[self.context_window]
            current_line = current_window["line_num"]
            self.yanked_lines.add(current_line)
            self.mode = 'line'
            self.status = 'mark'
            self.handle_down_arrow()
        else:
            current_window = self.windows[self.context_window]
            current_line = current_window["line_num"]
            if not self.yank_mode_active:
                self.yanked_lines.clear()
                self.yank_mode_active = True
            self.yanked_lines.add(current_line)
            self.mode = 'line'
            self.status = 'xtrac'
    def handle_ctrl_k(self):
        if self.context_window == 0 and self.mode == 'line':
            self.windows[0]["line_num"] += 38
            if self.windows[0]["line_num"] >= len(self.windows[0]["text"]):
                self.windows[0]["line_num"] = len(self.windows[0]["text"]) - 1
            if self.windows[0]["col_num"] > len(self.windows[0]["text"][self.windows[0]["line_num"]]):
               self.windows[0]["col_num"] = len(self.windows[0]["text"][self.windows[0]["line_num"]])
            self.adjust_window_offset()
        else:
            self.insert_char(ord('\\'))
    def handle_ctrl_y(self):
        if self.yank_mode_active and self.yanked_lines:
            current_window = self.windows[self.context_window]
            self.clipboard = [current_window["text"][line] for line in sorted(self.yanked_lines)]
            self.yanked_lines.clear()
            self.yank_mode_active = False
            self.mode = 'line'
            self.status = 'yankd'
    def handle_ctrl_p(self):
        if self.clipboard:
            current_window = self.windows[self.context_window]
            buffer = list(current_window["text"])
            current_line = current_window["text"][current_window["line_num"]]
            for line in self.clipboard:
                current_window["text"].insert(current_window["line_num"], line)
                current_window["line_num"] += 1
            current_window["col_num"] = len(current_line)
            self.clipboard = []
            self.clipboard = buffer
            self.mode = 'line'
            self.status = 'paste'
            self.adjust_window_offset()
    def handle_ctrl_v(self):
        self.context.reset()
        self.context.get_cogtext_by_name(self.cognalities.next_cognality())
        self.adjust_window_offset()
        self.display()
    def search_text(self):
        search_term = "\n".join(self.windows[1]["text"]).strip()
        if not search_term:
            self.status = 'no tm'
            return
        self.search_results.clear()
        top_window = self.windows[0]["text"]
        for i, line in enumerate(top_window):
            start_idx = 0
            while start_idx < len(line):
                start_idx = line.find(search_term, start_idx)
                if start_idx == -1:
                    break
                self.search_results.append((i, start_idx))
                start_idx += len(search_term)
        if self.search_results:
            self.current_search_result = 0
            self.highlight_search_result()
            self.status = f"fnd {len(self.search_results):02}"
            self.context_window = 0
        else:
            self.status = 'not f'
    def highlight_search_result(self):
        if not self.search_results:
            return
        line_num, col_num = self.search_results[self.current_search_result]
        self.windows[0]["line_num"] = line_num
        self.windows[0]["col_num"] = col_num
        self.adjust_window_offset()
    def next_search_result(self):
        if self.search_results:
            self.current_search_result = (self.current_search_result + 1) % len(self.search_results)
            self.highlight_search_result()
    def prev_search_result(self):
        if self.search_results:
            self.current_search_result = (self.current_search_result - 1) % len(self.search_results)
            self.highlight_search_result()
    def handle_sigint(self, sig, frame):
        self.stdscr.addstr(0, 0, "Ctrl-C, are you sure you want to exit? (Y/n):", curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.refresh()
        while True:
            ch = self.stdscr.getch()
            if ch == ord('Y'):
                raise SystemExit
            elif ch == ord('n') or ch == ord('N'):
                self.display()
                return
    def handle_ctrl_a(self):
        self.context_window = 1 - self.context_window
        if self.context_window == 1:
            self.mode = 'commd'
        else:
            self.mode = 'edit'
    def handle_ctrl_t(self):
        self.status = "Ctrlt"
        self.display()
    def handle_ctrl_m(self):
        self.mode = "not captured"
    def handle_ctrl_h(self):
        self.status = "CtrlH"
        self.display()
    def handle_ctrl_g(self):
        self.status = "CtrlG"
        self.display()
    def run(self):
        while True:
            self.display()
            ch = self.stdscr.getch()
            if ch == curses.KEY_UP:
                self.handle_up_arrow()
            elif ch == curses.KEY_DOWN:
                self.handle_down_arrow()
            elif ch == curses.KEY_RIGHT:
                self.handle_right_arrow()
            elif ch == curses.KEY_LEFT:
                self.handle_left_arrow()
            elif ch == ord('\\'):
                self.handle_backslash()
            elif ch == ord('\n'):
                self.handle_return()
            elif ch in (curses.KEY_BACKSPACE, 127):
                self.handle_backspace(ch)
            elif ch == 11:  # ctrl-k
                self.handle_ctrl_k()
            elif ch == 23:
                self.write_file()
            elif ch == 18:
                self.read_file()
            elif ch == 1:
                self.handle_ctrl_a()
            elif ch == 16:
                self.handle_ctrl_p()
            elif ch == 6:  # Ctrl-F
                self.search_text()
            elif ch == 22:  # Ctrl-v
                self.handle_ctrl_v()
            elif ch == 14:  # Ctrl-N
                self.next_search_result()
            elif ch == 2:  # Ctrl-B
                self.prev_search_result()
            elif ch == 4:
                self.delete_current_line()
            elif ch == 20:
                self.handle_ctrl_t()
            elif ch == 25:
                self.handle_ctrl_y()
            elif ch == 24:  # Ctrl-X
                self.handle_ctrl_x()
            elif ch == 8:   # Ctrl-H
                self.handle_ctrl_h()
            elif ch == 7:  # Ctrl-G
                self.handle_ctrl_g()
            else:
                if self.windows[self.context_window]["line_num"] >= len(self.windows[self.context_window]["text"]):
                    self.windows[self.context_window]["text"].append('')
                self.insert_char(ch)
    def show_splash_screen(self):
        self.stdscr.clear()
        self.status = 'splsh'
        splash_text = [
            "",
            "Welcome to the AIQuickKeyEditor!",
            "    qk for short ;)",
            "",
            "Control Characters:",
            "Ctrl-A: Switch between editor window and AI command.",
            "Ctrl-V: Switch AI Personality, E.g. Spelling and Grammar, Python Coder.",
            "Ctrl-W: Write the editor window to a file.",
            "Ctrl-R: Read the file to edit.",
            "Backslash key (\\): Quick Query AI.",
            "Backspace key (<-): Switch between the AI reply and the original, for quick comparison.",
            "Ctrl-D: Delete a line.",
            "Ctrl-X: Extract and mark lines (repeat Ctrl-X).",
            "Ctrl-Y: Yank (copy) the marked lines.",
            "Ctrl-P: Paste the yanked lines.",
            "Ctrl-K: If you need a backslash.",
            "Use the arrow keys to navigate.",
            "",
            "Try:",
            "Crtl-A to switch to the AI command window,",
            "Type: 'Print the Fibonacci series.'",
            "Crtl-V to change voice to Spelling.",
            "Depress the \\ key to fix spelling inline, in the AI command window,",
            "Be sure to Ctrl-A back to the editor window,",
            "Crtl-V to change to Python Coder.",
            "Press the \\ key to send your request to AI.",
            "",
            "Enjoy your AI-Assisted text and code writing experience!"
        ]
        splash_text_width = max(len(line) for line in splash_text) + 1
        splash_text_height = len(splash_text)
        screen_height, screen_width = self.stdscr.getmaxyx()
        for y, line in enumerate(splash_text):
            if y >= splash_text_height:
                break
            x = ((screen_width - splash_text_width) // 2) -2
            self.stdscr.addstr(y, x, line)
            self.stdscr.addstr(y, 0, f"{y + 1:03}<{self.mode:5}>", curses.A_REVERSE)
        self.mode = ''
        self.stdscr.refresh()
        self.stdscr.getch()

def main(stdscr):
    editor = AIQuickKeyEditor(stdscr)
    editor.run()
if __name__ == "__main__":
    curses.wrapper(main)


