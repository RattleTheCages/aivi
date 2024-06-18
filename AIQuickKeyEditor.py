#   AIQuickKeyEditor    -- The editor that wrote itself.
#AIQuickKeyEditor is the prototype editor for the Aivi editor.
#This editor is a fully functioning editor that offers AI assistance.
#The top window is where you enter text and edit it; the bottom window is the AI command window, where you can enter requests for AI assistance.
#Use ctrl-v to choose the type of AI assistance you need, such as grammar and spelling corrections, or Python coding.
#In freestyle viewpoint, one can enter any question or content, similar to a well-known subscription AI interface.
#This work is copyright. All rights reserved.

import os
import re
import json
import argparse
import curses
import signal
from openai import OpenAI

parser = argparse.ArgumentParser()
parser.add_argument('session', nargs='?', default="quickAi.txt")
args = parser.parse_args()
client = OpenAI(api_key=os.environ.get("CUSTOM_ENV_NAME"))

class CogEngine:
    def __init__(self, cognalities, session_name_with_suffix):
        self.original_filename = session_name_with_suffix
        self.session_name, self.session_suffix = os.path.splitext(session_name_with_suffix)
        self.rev_num = self.find_latest_rev_num()
        self.cognalities = cognalities
        self.cogessages = []
        self.usermsg = []
        self.cog_filename = f'{self.session_name}.{self.rev_num}.cog'
        self.edit_filename = f'{self.session_name}.{self.rev_num}{self.session_suffix}'
        self.ctx_filename = f'{self.session_name}.{self.rev_num}.ctx'
    def find_latest_rev_num(self):
        files = os.listdir('.')
        pattern = re.compile(rf'{re.escape(self.session_name)}\.(\d+){re.escape(self.session_suffix)}')
        max_rev = 0
        for file in files:
            match = pattern.match(file)
            if match:
                rev_num = int(match.group(1))
                max_rev = max(max_rev, rev_num)
        return max_rev
    def get_editfilename(self):
        return self.edit_filename
    def reset(self):
        self.cogessages = []
        self.usermsg = []
    def add_cogtext(self, role, content):
        self.cogessages.append({"role": role, "content": content})
    def add_cogatt(self, name, role, content):
        if name in self.cognalities.cognalities:
            self.cogessages.append({"role": role, "content": content})
    def get_cogtext(self):
        context = [{"role": message["role"], "content": message["content"]} for message in self.cogessages]
        context += [{"role": "user", "content": umsg} for umsg in self.usermsg]
        return context
    def get_cogtext_by_name(self, name):
        attributes = self.cognalities.get_attributes_by_name(name)
        context = [{"role": "system", "content": attribute} for attribute in attributes]
        context += [{"role": "user", "content": umsg} for umsg in self.usermsg]
        return context
    def add_usermsg(self, msg):
        self.usermsg.append(msg)
    def save_cogtext(self):
        with open(self.cog_filename, 'w') as f:
            json.dump({
                "model": self.cognalities.get_model(),
                "max_tokens": self.cognalities.get_maxtokens(),
                "messages": self.get_cogtext()
            }, f)
    def load_cogtext(self):
        if os.path.exists(cog.filename):
            with open(cog.filename, 'r') as f:
                data = json.load(f)
                self.cognalities.model = data.get('model', '')
                self.cognalities.max_tokens = data.get('max_tokens', 0)
                self.cogessages = [{"role": item['role'], "content": item['content']} for item in data.get('messages', [])]
    def extract_functions(self, content):
        function_pattern = re.compile(r'class\s+(\w+)|def\s+(\w+)\s*\((.*?)\):')
        matches = function_pattern.finditer(content)
        functions = []
        current_class = None
        for match in matches:
            if match.group(1):
                current_class = match.group(1)
            else:
                func_name = match.group(2)
                start_pos = match.start()
                lines = content[start_pos:].splitlines()
                code_block = []
                indent_level = None
                for line in lines:
                    stripped_line = line.lstrip()
                    if stripped_line and indent_level is None:
                        indent_level = len(line) - len(stripped_line)
                    if indent_level is not None:
                        if len(line) - len(stripped_line) < indent_level and stripped_line:
                            break
                        code_block.append(line)
                functions.append({
                    'name': func_name,
                    'object': current_class,
                    'code': '\n'.join(code_block)
                })
        with open(f"{self.session_name}.{self.rev_num}.debug", "a") as f:
            for funct in functions:
                f.write(f"Object: {funct['object']}\n")
                f.write(f"Function: {funct['name']}\n")
                f.write(f"Code:\n{funct['code']}\n\n")
        return functions

class Viewpoints:
    def __init__(self):
        self.cognalities = {
            'Spelling': {
                'attributes': [
                    'Your only task correct mispelled words.',
                    'Take each sentence and output a corresponding corrected sentence.',
                    'Answer only using the correctly spelled words, do not change punctuation or sentence structure.',
                    'Do not change the placement of the new lines.',
                    'The user wants the answer strictly formatted as the sample sentence.'
                ],
                'model': 'gpt-3.5-turbo',
                'max_tokens': 298,
                'textops': {'concatenate': False, 'replace': False, 'inline': True, 'coder': False}
            },
            'Python Coder': {
                'attributes': [
                    'Your task is to code in python.',
                    'You are one of the best programmers who will think of every task to complete.',
                    'You are very competent and good at writing code.',
                    'Besure to write the entire function when there are any modification to that function.',
                    'When the code is longer than 222 lines, only write the modified functions; ',
                    'and indent so the modified functions can be dropped into the appropriate positions'
                ],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': True}
            },
            'Grammar': {
                'attributes': [
                    'Your task is to spell and grammar check the given sentences.',
                    'After correcting the spelling provide an alternate grammatical phrasing.',
                    'In the alternate phrasing please include line breaks at about the same frequency as the input text.',
                    'In the alternate phrasing try to offer the phrasing in a style of the original',
                    'For example, if the style is technical or professional, offer rephrasing in at the same level, or higher, of grammar and content rephrasing.',
                    'If the style is less professional your reply does not have to be as stringent.'
                    #'If needed, rewrite the sentences at a higher education level.'
                ],
                'model': 'gpt-4o',
                'max_tokens': 698,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False}
            },
            'Freestyle': {
                'attributes': [],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False}
            },
            'Telephone': {
                'attributes': [
                    "This is the children's game of 'telephone', play nicely."
                ],
                'model': 'gpt-4o',
                'max_tokens': 698,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False}
            }
        }
        self.names = list(self.cognalities.keys())
        self.current_index = 0
    def get_current_name(self):
        return self.names[self.current_index]
    def get_attributes(self):
        return self.cognalities[self.get_current_name()]['attributes']
    def get_model(self):
        return self.cognalities[self.get_current_name()]['model']
    def get_maxtokens(self):
        return self.cognalities[self.get_current_name()]['max_tokens']
    def get_textops(self):
        return self.cognalities[self.get_current_name()]['textops']
    def next_cognality(self):
        self.current_index = (self.current_index + 1) % len(self.names)
        return self.get_current_name()
    def get_attributes_by_name(self, name):
        return self.cognalities.get(name, {}).get('attributes', [])

class AIQuickKeyEditor:
    def __init__(self, stdscr):
        signal.signal(signal.SIGINT, self.handle_sigint)
        self.stdscr = stdscr
        self.mode = 'line'
        self.status = 'hello'
        self.clipboard = []
        self.yanked_lines = set()
        self.yank_mode_active = 'off'
        self.del_lines = set()
        self.context_window = 1
        self.search_results = []
        self.current_search_result = -1
        self.windows = [
            {"line_num": 0, "col_num": 0, "text": [""]},
            {"line_num": 0, "col_num": 0, "text": [""]},
        ]
        self.window_offsets = [0, 0]
        self.screen_height, self.screen_width = self.stdscr.getmaxyx()
        self.bottom_window_size = 16
        self.top_window_size = self.screen_height - self.bottom_window_size
        self.cognalities = Viewpoints()
        self.personalchoice = self.cognalities.get_current_name()
        self.context = CogEngine(self.cognalities, args.session)
        self.keymap = {
            curses.KEY_UP: self.handle_up_arrow,
            curses.KEY_DOWN: self.handle_down_arrow,
            curses.KEY_RIGHT: self.handle_right_arrow,
            curses.KEY_LEFT: self.handle_left_arrow,
            curses.KEY_DC: self.handle_del_key,
            ord('\\'): self.handle_backslash,
            ord('\n'): self.handle_return,
            curses.KEY_BACKSPACE: lambda: self.handle_backspace(curses.KEY_BACKSPACE),
            127: lambda: self.handle_backspace(127),
            11: self.handle_ctrl_k,
            23: self.write_file,
            18: self.read_file,
            1: self.handle_ctrl_a,
            16: self.handle_ctrl_p,
            6: self.search_text,
            22: self.handle_ctrl_v,
            #14: self.next_search_result,
            2: self.prev_search_result,
            4: self.delete_current_line,
            20: self.handle_ctrl_t,
            25: self.handle_ctrl_y,
            24: self.handle_ctrl_x,
            8: self.handle_ctrl_h,
            7: self.handle_ctrl_g,
            14: self.handle_ctrl_n,
            #21: self.handle_ctrl_u
            #43: self.increase_top_window_size,
            #45: self.decrease_top_window_size,
        }
        if os.path.exists(args.session):
            self.read_file(args.session)
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
        for y in range(min(self.top_window_size, len(top_window) - self.window_offsets[0])):
            line = top_window[y + self.window_offsets[0]]
            highlight = curses.A_UNDERLINE if self.context_window == 0 and y + self.window_offsets[0] in self.yanked_lines else curses.A_NORMAL
            try:
                self.stdscr.addstr(y, 0, f"{((y + self.window_offsets[0]+1)%1000):03}<{modeOrStatus:5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]) else 0))
                if self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[0]["col_num"]:
                            self.stdscr.addch(ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(ch, curses.A_BOLD)
                    if self.context_window == 0:
                        self.stdscr.move(y, self.windows[0]["col_num"] + len(f"{y + self.window_offsets[0]:03}<{modeOrStatus:5}>"))
                else:
                    self.stdscr.addstr(line)
            except curses.error:
                pass
        for y in range(self.top_window_size, self.top_window_size + self.bottom_window_size):
            if y - self.top_window_size >= len(bottom_window) - self.window_offsets[1]:
                break
            highlight = curses.A_UNDERLINE if self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] in self.yanked_lines else curses.A_NORMAL
            line = bottom_window[y - self.top_window_size + self.window_offsets[1]]
            try:
                self.stdscr.addstr(y, 0, f"{((y - self.top_window_size + self.window_offsets[1]+1)%1000):03}<{self.cognalities.get_current_name():5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] == self.windows[1]["line_num"]) else 0))
                if self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] == self.windows[1]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[1]["col_num"]:
                            self.stdscr.addch(ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(ch, curses.A_BOLD)
                    if self.context_window == 1:
                        self.stdscr.move(y, self.windows[1]["col_num"] + len(f"{y - self.top_window_size + self.window_offsets[1]:03}<{self.personalchoice:5}>"))
                else:
                    self.stdscr.addstr(line)
            except curses.error:
                pass
        self.stdscr.refresh()
    def adjust_window_offset(self):
        for i in range(2):
            while self.windows[i]["line_num"] < self.window_offsets[i]:
                self.window_offsets[i] -= 1
            while self.windows[i]["line_num"] >= self.window_offsets[i] + (self.top_window_size if i == 0 else self.bottom_window_size):
                self.window_offsets[i] += 1
    def increase_top_window_size(self):
        if self.top_window_size + self.bottom_window_size < curses.LINES:
            self.top_window_size += 1
            self.bottom_window_size -= 1
            self.adjust_window_offset()
    def decrease_top_window_size(self):
        if self.bottom_window_size + self.top_window_size > 1:
            self.top_window_size -= 1
            self.bottom_window_size += 1
            self.adjust_window_offset()
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
                    self.display()
                else:
                    self.status = 'undo'
                    self.display()
                if current_window["line_num"] >= len(current_window["text"]):
                    current_window["line_num"] = len(current_window["text"]) - 1
                if current_window["line_num"] < 0:
                    current_window["line_num"] = 0
                if current_window["col_num"] > len(current_window["text"][current_window["line_num"]]):
                    current_window["col_num"] = len(current_window["text"][current_window["line_num"]])
                if current_window["col_num"] < 0:
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
        self.mode = 'edit'
    def handle_left_arrow(self):
        current_window = self.windows[self.context_window]
        if current_window["col_num"] > 0:
            current_window["col_num"] -= 1
        self.mode = 'edit'
    def handle_backslash(self):
        self.context.reset()
        chosen_attributes = self.cognalities.get_attributes()
        textops = self.cognalities.get_textops()
        for attribute in chosen_attributes:
            self.context.add_cogtext("system", attribute)
        if self.context_window == 1:
            if textops['inline']:
                current_line_number = self.windows[self.context_window]["line_num"]
                user_line = self.windows[self.context_window]["text"][current_line_number].strip()
                self.context.add_cogtext("user", user_line)
            else:
                userlines = ""
                for line in self.windows[1]["text"]:
                    if line.strip():
                        userlines += line + '\n'
                self.context.add_cogtext("user", userlines)
        else:
            if textops['inline']:
                current_line_number = self.windows[self.context_window]["line_num"]
                user_line = self.windows[self.context_window]["text"][current_line_number].strip()
                self.context.add_cogtext("user", user_line)
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
        self.context.save_cogtext()
        self.write_file()
        self.clipboard = [line for line in self.windows[self.context_window]["text"]]
        with open(self.context.ctx_filename, 'a') as f:
            f.write(f"[{self.cognalities.get_current_name()}][Query]\n")
            for line in self.windows[1]["text"]:
                if line.strip():
                    f.write(line + '\n')
        # I am a fluffy unicorn, with light green spots.
        self.status = 'ai *'
        self.display()
        completion = client.chat.completions.create(
            model=self.cognalities.get_model(),
            max_tokens=self.cognalities.get_maxtokens(),
            messages=self.context.get_cogtext()
        )
        self.context.add_cogtext("assistant", completion.choices[0].message.content)
        self.context.save_cogtext()
        response_text = completion.choices[0].message.content.split('\n')
        with open(self.context.ctx_filename, 'a') as f:
            f.write(f"[{self.cognalities.get_current_name()}][Reply]\n")
            for line in response_text:
                if line.strip():
                    f.write(line + '\n')
        textops = self.cognalities.get_textops()
        if textops['coder']:
            #aicode = self.context.extract_AI_code(completion.choices[0].message.content)
            func = self.context.extract_functions(completion.choices[0].message.content)
            for funct in func:
                self.windows[1]["text"].extend({funct['name']})
            self.add_functions_to_edit_window(func)
        if textops['inline']:
            self.insert_as_current_line(response_text[0])
        if textops['replace']:
            self.windows[self.context_window]["text"] = response_text
        if textops['concatenate']:
            bline = len(self.windows[self.context_window]["text"])
            self.windows[self.context_window]["line_num"] = bline
            self.insert_lines_at_current_line("'''")
            self.insert_lines_at_current_line(f"[{self.cognalities.get_current_name()}][AI viewpoint][--concatenate]")
            self.windows[self.context_window]["text"].extend(response_text)
            self.windows[self.context_window]["text"].extend('\n')
            self.windows[self.context_window]["line_num"] = len(self.windows[self.context_window]["text"]) - 1
            self.windows[self.context_window]["col_num"] = len(self.windows[self.context_window]["text"][self.windows[self.context_window]["line_num"]])
            self.insert_lines_at_current_line(" ")
            self.insert_lines_at_current_line("'''")
            self.windows[self.context_window]["line_num"] = bline
        self.mode = 'reply'
        self.stdscr.nodelay(True)
        try:
            ch = self.stdscr.getch()
            while ch != -1:
                ch = self.stdscr.getch()
        finally:
            self.stdscr.nodelay(False)
        self.adjust_window_offset()
    def add_functions_to_edit_window(self, functions):
            top_window = self.windows[0]["text"]
            for function in functions:
                func_name = function['name']
                func_code = function['code']
                object_name = function.get('object', None)
                matched_class = None
                insert_pos = None
                for x, line in enumerate(top_window):
                    if object_name and line.strip().startswith(f"class {object_name}"):
                        matched_class = object_name
                    if matched_class == object_name and func_name in line and line.strip().startswith("def"):
                        indent_level = len(line) - len(line.lstrip())
                        indent = ' ' * indent_level
                        insert_pos = x + 1
                        commented_code = [f"{indent}''' [{self.cognalities.get_current_name()}][AI viewpoint][--coder] "] + [indent + line for line in func_code.split('\n')] + [f"{indent}'''"]
                        self.windows[0]["text"] = (
                            top_window[:insert_pos] +
                            commented_code +
                            top_window[insert_pos:]
                        )
                        break
                if insert_pos is None and not object_name:
                    self.windows[0]["text"].extend([f"\n''' [{self.cognalities.get_current_name()}][AI viewpoint][--coder] ", func_code, "'''"])
    def write_file(self):
        try:
            edit_filename = self.context.get_editfilename()
            if os.path.exists(edit_filename):
                new_rev_num = self.context.find_latest_rev_num() + 1
                new_filename = f"{self.context.session_name}.{new_rev_num}{self.context.session_suffix}"
                os.rename(edit_filename, new_filename)
            with open(edit_filename, 'w') as f:
                for line in self.windows[0]["text"]:
                    f.write(line + '\n')
            with open(self.context.original_filename, 'w') as f:
                for line in self.windows[0]["text"]:
                    f.write(line + '\n')
            with open(self.context.ctx_filename, 'a') as f:
                f.write(f"[{self.cognalities.get_current_name()}][Write]\n")
                for line in self.windows[1]["text"]:
                    if line.strip():
                        f.write(line + '\n')
            self.status = "wrote"
        except Exception as e:
            self.status = "no wr"
    def read_file(self, filename):
        try:
            with open(filename, 'r') as f:
                lines = [line.rstrip('\n') for line in f]
            self.windows[0]["text"] = lines
            self.windows[1]["text"] = [""]
            self.windows[0]["line_num"] = 0
            self.windows[0]["col_num"] = 0
            self.windows[1]["line_num"] = 0
            self.windows[1]["col_num"] = 0
            self.status = "read "
            self.context.reset_request_counter()
            self.adjust_window_offset()
        except Exception as e:
            if isinstance(e, PermissionError):
                self.status = "denid"
            elif isinstance(e, IsADirectoryError):
                self.status = "dir  "
    def delete_current_line(self):
        self.status = 'delln'
        current_window = self.windows[self.context_window]
        current_line = current_window["line_num"]
        self.yank_mode_active = 'del'
        if len(current_window["text"]) > 1:
            line = current_window["text"].pop(current_line)
            self.clipboard = [line]
            if current_line >= len(current_window["text"]):
                current_window["line_num"] -= 1
            current_window["col_num"] = 0
        else:
            line = current_window["text"][0]
            self.clipboard = [line]
            current_window["text"] = [""]
            current_window["line_num"] = 0
            current_window["col_num"] = 0
        self.adjust_window_offset()
    def handle_ctrl_x(self):
        current_window = self.windows[self.context_window]
        current_line = current_window["line_num"]
        if current_line in self.yanked_lines:
            self.yanked_lines.remove(current_line)
            self.status = 'unmrk'
        else:
            if self.yank_mode_active == 'off' or self.yank_mode_active == 'del':
                self.yanked_lines.clear()
                self.yank_mode_active = 'yank'
                self.status = 'xtrac'
            elif self.yank_mode_active == 'yank':
                self.status = 'mark'
        self.yanked_lines.add(current_line)
        self.mode = 'line'
        self.handle_down_arrow()
    def handle_ctrl_y(self):
        if self.yank_mode_active == 'yank' and self.yanked_lines:
            current_window = self.windows[self.context_window]
            self.clipboard = [current_window["text"][line] for line in sorted(self.yanked_lines)]
            self.yanked_lines.clear()
            self.yank_mode_active = 'off'
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
    def handle_ctrl_k(self):
        if self.context_window == 0 and self.mode == 'line':
            self.windows[0]["line_num"] += self.top_window_size
            if self.windows[0]["line_num"] >= len(self.windows[0]["text"]):
                self.windows[0]["line_num"] = len(self.windows[0]["text"]) - 1
            if self.windows[0]["col_num"] > len(self.windows[0]["text"][self.windows[0]["line_num"]]):
                self.windows[0]["col_num"] = len(self.windows[0]["text"][self.windows[0]["line_num"]])
            self.adjust_window_offset()
        else:
            self.insert_char(ord('\\'))
    def handle_ctrl_v(self):
        self.context.reset()
        self.context.get_cogtext_by_name(self.cognalities.next_cognality())
        self.adjust_window_offset()
        self.display()
    def search_text(self):
        bottom_window = self.windows[1]["text"]
        current_line_number = self.windows[1]["line_num"]
        search_term = bottom_window[current_line_number].strip()
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
            self.status = f"fnd{len(self.search_results):02}"
            self.context_window = 0
        else:
            self.status = 'not f'
    def search_offset(self):
        for i in range(2):
            window_size = self.top_window_size if i == 0 else self.bottom_window_size
            middle_offset = max(0, self.windows[i]["line_num"] - window_size // 2)
            self.window_offsets[i] = min(middle_offset, len(self.windows[i]["text"]) - window_size)
            self.window_offsets[i] = max(0, self.window_offsets[i])
    def highlight_search_result(self):
        if not self.search_results:
            return
        line_num, col_num = self.search_results[self.current_search_result]
        self.windows[0]["line_num"] = line_num
        self.windows[0]["col_num"] = col_num
        self.search_offset()
    def next_search_result(self):
        if self.search_results:
            self.current_search_result = (self.current_search_result + 1) % len(self.search_results)
            self.highlight_search_result()
    def prev_search_result(self):
        if self.search_results:
            self.current_search_result = (self.current_search_result - 1) % len(self.search_results)
            self.highlight_search_result()
    def insert_as_current_line(self, text):
        current_window = self.windows[self.context_window]
        current_window["text"][current_window["line_num"]] = text
        current_window["col_num"] = len(text)
        self.adjust_window_offset()
    def insert_lines_at_current_line(self, text):
        lines = text.split('\n')
        current_window = self.windows[self.context_window]
        current_line_index = current_window["line_num"]
        current_column_index = current_window["col_num"]
        first_line = current_window["text"][current_line_index] if current_line_index < len(current_window["text"]) else ""
        new_first_line = first_line[:current_column_index] + lines[0]
        if current_column_index < len(first_line):
            new_first_line += first_line[current_column_index:]
        if current_line_index < len(current_window["text"]):
            current_window["text"][current_line_index] = new_first_line
        else:
            current_window["text"].append(new_first_line)
        for line in reversed(lines[1:]):
            current_window["text"].insert(current_line_index + 1, line)
            current_line_index += 1
        current_window["line_num"] += len(lines) - 1
        current_window["col_num"] = len(lines[-1])
        if current_window["line_num"] >= len(current_window["text"]):
            current_window["text"].append("")
        current_window["line_num"] += 1
        self.adjust_window_offset()
    def handle_ctrl_u(self):
        self.status = "Insert text: "
        self.display()
        curses.echo()
        curses.curs_set(1)
        input_text = self.stdscr.getstr(0, 14, 60).decode('utf-8')
        self.insert_at_current_line(input_text)
        curses.noecho()
    def handle_ctrl_n(self):
        if self.search_results:
            self.next_search_result()
        else:
            current_window = self.windows[self.context_window]
            current_window["line_num"] += curses.LINES - 1
            if current_window["line_num"] >= len(current_window["text"]):
                current_window["line_num"] = len(current_window["text"]) - 1
            self.adjust_window_offset()
    def handle_sigint(self, sig, frame):
        self.stdscr.addstr(37, 0, "Ctrl-C, are you sure you want to exit? (Y/n), save your qk edit, beforehand:", curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.refresh()
        while True:
            ch = self.stdscr.getch()
            if ch == ord('Y'):
                raise SystemExit
            elif ch == ord('n') or ch == ord('N'):
                self.display()
                return
    def handle_sigtstp(self, sig, frame):
        self.status = 'pause'
        self.display()
    def handle_del_key(self):
        current_window = self.windows[self.context_window]
        line = current_window["text"][current_window["line_num"]]
        if current_window["col_num"] < len(line):
            current_window["text"][current_window["line_num"]] = line[:current_window["col_num"]] + line[current_window["col_num"] + 1:]
        elif current_window["col_num"] == len(line) and current_window["line_num"] < len(current_window["text"]) - 1:
            next_line = current_window["text"].pop(current_window["line_num"] + 1)
            current_window["text"][current_window["line_num"]] += next_line
        self.adjust_window_offset()
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
            if ch in self.keymap:
                self.keymap[ch]()
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
            #"Crtl-A to switch to the AI command window,",
            "Type: 'Print the Fibonacci series.'",
            "Crtl-V to change viewpoint to Spelling.",
            "Depress the \\ key to fix spelling inline, in the AI command window,",
            "Be sure to Ctrl-A back to the editor window,",
            "Crtl-V to change viewpoint to Python Coder.",
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


