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
import subprocess
from openai import OpenAI

parser = argparse.ArgumentParser()
parser.add_argument('session', nargs='?', default="quickAi.txt")
args = parser.parse_args()
client = OpenAI(api_key=os.environ.get("CUSTOM_ENV_NAME"))

class CogEngine:
    def __init__(self, cognalities, edit_session):
        self.cognalities = cognalities
        self.cogessages = []
        self.usermsg = []
        self.edit_session = edit_session
    def reset(self, viewpoint):
        self.cogessages = []
        self.usermsg = []
        for attribute in viewpoint.get_attributes():
            self.add_cogtext("system", attribute)
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
    def ai_query(self, viewpoint):
        reform = client.chat.completions.create(
            model = viewpoint.get_model(),
            max_tokens = viewpoint.get_maxtokens(),
            messages = self.get_cogtext()
        )
        self.add_cogtext("assistant", reform.choices[0].message.content)
        return reform
    def save_cogtext(self):
        with open(self.edit_session.cog_filename, 'w') as cogf:
            json.dump({
                "model": self.cognalities.get_model(),
                "max_tokens": self.cognalities.get_maxtokens(),
                "messages": self.get_cogtext()
            }, cogf)
    def extract_objects(self, content):
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
                        if '```' in line:
                            break
                        stripped_line = line.lstrip()
                        if stripped_line.startswith('def') and code_block:
                            break
                        if stripped_line.startswith('class') and code_block:
                            break
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
            with open(f"{self.edit_session.session_name}.{self.edit_session.rev_num}.debug", "a") as f:
                for funct in functions:
                    f.write(f"Object: {funct['object']}\n")
                    f.write(f"Function: {funct['name']}\n")
                    f.write(f"Code:\n{funct['code']}\n")
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
                'textops': {'concatenate': False, 'replace': False, 'inline': True, 'coder': False, 'refactor': False}
            },
            'Python Coder': {
                'attributes': [
                    'Your task is to code in python.',
                    'You are one of the best programmers who will think of every task to complete.',
                    'You are very competent and good at writing code.',
                    'Besure to write the entire function when there are any modification to that function.',
                    'When the code is longer than 222 lines, only write the modified functions; ',
                    'and indent so the modified functions can be dropped into the appropriate positions',
                    'Besure to write the class or object the modified function belongs to.'
                ],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                #'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': True, 'refactor': False}
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': True, 'refactor': True}
            },
            'Grammar': {
                'attributes': [
                    'Your task is to spell and grammar check the given sentences.',
                    'After correcting the spelling provide an alternate grammatical phrasing.',
                    'In the alternate phrasing please include line breaks at about the same frequency as the input text.',
                    'In the alternate phrasing try to offer the phrasing in a style of the original',
                    'For example, if the style is technical or professional, offer rephrasing in at the same level, or higher, of grammar and content rephrasing.',
                    'If the style is less professional your reply does not have to be as stringent.'
                ],
                'model': 'gpt-4o',
                'max_tokens': 698,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False, 'refactor': False}
            },
            'Freestyle': {
                'attributes': [],
                'model': 'gpt-4o',
                'max_tokens': 4096,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False, 'refactor': False}
            },
            'Telephone': {
                'attributes': [
                    "This is the children's game of 'telephone', play nicely."
                ],
                'model': 'gpt-3.5-turbo',
                'max_tokens': 298,
                'textops': {'concatenate': True, 'replace': False, 'inline': False, 'coder': False, 'refactor': False}
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

class EditRevisionManager:
    def __init__(self, session_name_with_suffix):
        self.revisions = {}
        self.subrevisions = {}
        self.original_filename = session_name_with_suffix
        self.session_name, self.session_suffix = os.path.splitext(session_name_with_suffix)
        self.rev_num = self.find_latest_file_rev_num() + 1
        self.cog_filename = f'{self.session_name}.{self.rev_num}.cog.json'
        self.edit_filename = f'{self.session_name}.{self.rev_num}{self.session_suffix}'
        self.ctx_filename = f'{self.session_name}.{self.rev_num}.ctx'
        self.subrev_num = 0
    def store_revision(self, rev_num, text):
        self.revisions[rev_num] = list(text)
    def get_revision(self, rev_num):
        return self.revisions.get(rev_num, [])
    def get_latest_revision(self):
        if self.revisions:
            max_rev_num = max(self.revisions.keys())
            return self.revisions[max_rev_num]
        return []
    def store_subrevision(self, subrev_text):
        self.subrev_num += 1
        self.subrevisions[self.subrev_num] = list(subrev_text)
        subrev_filename = f'{self.session_name}.{self.rev_num}.{self.subrev_num}.subrev'
        with open(subrev_filename, 'w') as f:
            for line in subrev_text:
                f.write(line + '\n')
    def find_latest_file_rev_num(self):
        files = os.listdir('.')
        suffixes = [self.session_suffix, '.cog.json', '.ctx']
        pattern = re.compile(rf'{re.escape(self.session_name)}\.(\d+)(?:{re.escape(self.session_suffix)}|\.cog\.json|\.ctx)')
        max_rev = 0
        for file in files:
            for suffix in suffixes:
                if file.endswith(suffix):
                    match = re.match(rf'{re.escape(self.session_name)}\.(\d+)', file)
                    if match:
                        rev_num = int(match.group(1))
                        max_rev = max(max_rev, rev_num)
        return max_rev
    def increment_rev(self):
        self.rev_num = self.find_latest_file_rev_num() + 1
        self.cog_filename = f'{self.session_name}.{self.rev_num}.cog.json'
        self.edit_filename = f'{self.session_name}.{self.rev_num}{self.session_suffix}'
        self.ctx_filename = f'{self.session_name}.{self.rev_num}.ctx'
    def write_file(self, viewpoint, edit_window_content, command_window_content):
        self.increment_rev()
        self.store_revision(self.rev_num, edit_window_content)
        if os.path.exists(self.original_filename):
            os.rename(self.original_filename, self.edit_filename + ".org")
        try:
            with open(self.original_filename, 'w') as og:
                for line in edit_window_content:
                    og.write(line + '\n')
            with open(self.edit_filename, 'w') as f:
                for line in edit_window_content:
                    f.write(line + '\n')
            with open(self.ctx_filename, 'a') as ctxf:
                for line_num, line in enumerate(command_window_content, start=1):
                    self.write_ctx_file_line(line, line_num, viewpoint, 'Write')
        except Exception as e:
            return "no wr"
        finally:
            return "wrote"
    def read_file(self):
        try:
            with open(self.original_filename, 'r') as og:
                lines = [line.rstrip('\n') for line in og]
            return "read ", lines
        except Exception as e:
            if isinstance(e, PermissionError):
                return "denid",
            elif isinstance(e, IsADirectoryError):
                return "dir  "
    def write_ctx_file_line(self, line, line_num, viewpoint, action):
            with open(self.ctx_filename, 'a') as ctxf:
                ctxf.write(f"{line_num:03}<[{viewpoint.get_current_name()}][{action}]{line}\n")

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
        self.show_left_column = True
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
        self.revision_manager = EditRevisionManager(args.session)
        self.context = CogEngine(self.cognalities, self.revision_manager)
        self.keymap = {
            curses.KEY_UP: self.handle_up_arrow,
            curses.KEY_DOWN: self.handle_down_arrow,
            curses.KEY_RIGHT: self.handle_right_arrow,
            curses.KEY_LEFT: self.handle_left_arrow,
            curses.KEY_DC: self.handle_del_key,
            curses.KEY_END: self.handle_end_key,
            curses.KEY_HOME: self.handle_home_key,
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
            5: self.handle_ctrl_e,
            17: self.handle_ctrl_q
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
            line = line[:self.screen_width]
            highlight = curses.A_UNDERLINE if self.context_window == 0 and y + self.window_offsets[0] in self.yanked_lines else curses.A_NORMAL
            try:
                if self.show_left_column:
                    self.stdscr.addstr(y, 0, f"{((y + self.window_offsets[0]+1)%1000):03}<{modeOrStatus:5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]) else 0))
                    start_text_pos = len(f"{((y + self.window_offsets[0]+1)%1000):03}<{modeOrStatus:5}>")
                else:
                    start_text_pos = 0
                if self.context_window == 0 and y + self.window_offsets[0] == self.windows[0]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[0]["col_num"]:
                            self.stdscr.addch(y, start_text_pos + x, ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(y, start_text_pos + x, ch, curses.A_BOLD)
                    if self.windows[0]["col_num"] == len(line):
                        self.stdscr.addch(y, start_text_pos + self.windows[0]["col_num"], ' ', curses.A_REVERSE | curses.A_NORMAL)
                    if self.context_window == 0:
                        self.stdscr.move(y, start_text_pos + self.windows[0]["col_num"])
                else:
                    self.stdscr.addstr(y, start_text_pos, line)
            except curses.error:
                pass
        for y in range(self.top_window_size, self.top_window_size + self.bottom_window_size):
            if y - self.top_window_size >= len(bottom_window) - self.window_offsets[1]:
                break
            highlight = curses.A_UNDERLINE if self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] in self.yanked_lines else curses.A_NORMAL
            line = bottom_window[y - self.top_window_size + self.window_offsets[1]]
            line = line[:self.screen_width]
            try:
                if self.show_left_column:
                    self.stdscr.addstr(y, 0, f"{((y - self.top_window_size + self.window_offsets[1]+1)%1000):03}<{self.cognalities.get_current_name():5}>", highlight | curses.A_REVERSE | (curses.A_BOLD if (self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] == self.windows[1]["line_num"]) else 0))
                    start_text_pos = len(f"{((y - self.top_window_size + self.window_offsets[1]+1)%1000):03}<{self.cognalities.get_current_name():5}>")
                else:
                    start_text_pos = 0
                if self.context_window == 1 and y - self.top_window_size + self.window_offsets[1] == self.windows[1]["line_num"]:
                    for x, ch in enumerate(line):
                        if x == self.windows[1]["col_num"]:
                            self.stdscr.addch(y, start_text_pos + x, ch, curses.A_REVERSE | curses.A_NORMAL)
                        else:
                            self.stdscr.addch(y, start_text_pos + x, ch, curses.A_BOLD)
                    if self.windows[1]["col_num"] == len(line):
                        self.stdscr.addch(y, start_text_pos + self.windows[1]["col_num"], ' ', curses.A_REVERSE | curses.A_NORMAL)
                    if self.context_window == 1:
                        self.stdscr.move(y, start_text_pos + self.windows[1]["col_num"])
                else:
                    self.stdscr.addstr(y, start_text_pos, line)
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
            self.context.reset(self.cognalities)
            textops = self.cognalities.get_textops()
            current_line_number = self.windows[self.context_window]["line_num"]
            if textops['inline']:
                user_line = self.windows[self.context_window]["text"][current_line_number].strip()
                self.revision_manager.write_ctx_file_line(user_line, current_line_number, self.cognalities, 'Query')
            else:
                self.write_file()
            if self.context_window == 1:
                if textops['inline']:
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
            self.clipboard = [line for line in self.windows[self.context_window]["text"]]
            # I am a fluffy unicorn, with light green spots.
            self.status = 'ai *'
            self.display()
            ai_revise = self.context.ai_query(self.cognalities)
            self.context.save_cogtext()
            response_text = ai_revise.choices[0].message.content.split('\n')
            if textops['inline']:
                self.revision_manager.write_ctx_file_line(response_text[0], current_line_number, self.cognalities, 'Reply')
                self.insert_as_current_line(response_text[0])
            if textops['coder']:
                #aicode = self.context.extract_AI_code(ai_revise.choices[0].message.content)
                func = self.context.extract_objects(ai_revise.choices[0].message.content)
                for funct in func:
                    self.windows[1]["text"].extend({funct['name']})
                self.add_objects_to_edit_window(func, textops)
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
            self.revision_manager.store_subrevision(self.windows[self.context_window]["text"])
            self.adjust_window_offset()
    def add_objects_to_edit_window(self, objects, textops):
        top_window = self.windows[0]["text"]
        if textops['refactor']:
            for function in objects:
                func_name = function['name']
                func_code = function['code']
                object_name = function.get('object', None)
                matched_class = None
                insert_pos = None
                end_pos = None
                for x, line in enumerate(top_window):
                    if object_name and line.strip().startswith(f"class {object_name}"):
                        matched_class = object_name
                    if matched_class == object_name and func_name in line and re.match(r'^\s*def\b', line):
                        indent_level = len(line) - len(line.lstrip())
                        indent = ' ' * indent_level
                        insert_pos = x
                        for i, end_line in enumerate(top_window[x+1:], start=x+1):
                            if re.match(r'^\s*(def|class)\b', end_line):
                                end_pos = i
                                break
                        if end_pos is None:
                            end_pos = len(top_window)
                        commented_code = [f"{indent}''' [{self.cognalities.get_current_name()}][AI viewpoint][--original]"] + [indent + l for l in top_window[insert_pos:end_pos]] + [f"{indent}'''"]
                        refactored_code = [f"{indent}#[{self.cognalities.get_current_name()}][AI viewpoint][--refactor] \n"]
                        refactored_code += [indent + l for l in func_code.split('\n')]
                        refactored_code += [f"{indent}"]
                        top_window[:] = (
                            top_window[:insert_pos] +
                            commented_code + refactored_code +
                            top_window[end_pos:]
                        )
                        break
                if insert_pos is None and not object_name:
                    self.windows[0]["text"].extend([f"\n''' [{self.cognalities.get_current_name()}][AI viewpoint][--renew] \n''' ", func_code, ""])
        else:
            top_window = self.windows[0]["text"]
            for function in objects:
                func_name = function['name']
                func_code = function['code']
                object_name = function.get('object', None)
                matched_class = None
                insert_pos = None
                end_pos = None
                for x, line in enumerate(top_window):
                    if object_name and line.strip().startswith(f"class {object_name}"):
                        matched_class = object_name
                    if matched_class == object_name and func_name in line and re.match(r'^\s*(def|class)\b', line):
                        indent_level = len(line) - len(line.lstrip())
                        indent = ' ' * indent_level
                        insert_pos = x
                        for i, end_line in enumerate(top_window[x:], start=x):
                            if end_line.strip().startswith('def ') or end_line.strip().startswith('class '):
                                end_pos = i
                                break
                        if end_pos is None:
                            end_pos = len(top_window)
                        commented_code = [f"{indent}''' [{self.cognalities.get_current_name()}][AI viewpoint][--new] "] + [indent + l for l in func_code.split('\n')] + [f"{indent}'''"]
                        top_window[:] = (
                            top_window[:insert_pos] +
                            commented_code +
                            top_window[end_pos:]
                        )
                        break
                if insert_pos is None and not object_name:
                    self.windows[0]["text"].extend([f"\n''' [{self.cognalities.get_current_name()}][AI viewpoint][--coder] ", func_code, "'''"])
    def write_file(self):
        self.status = self.revision_manager.write_file(self.cognalities, self.windows[0]["text"], self.windows[1]["text"])
    def read_file(self, filename):
        self.status, self.windows[0]["text"] = self.revision_manager.read_file()
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
        self.context.reset(self.cognalities)
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
        self.stdscr.addstr(38, 0, f'Ctrl-C, are you sure you want to exit? (Q/n/W), save your qk edit [{self.revision_manager.original_filename}], beforehand.', curses.A_REVERSE | curses.A_BOLD)
        self.stdscr.refresh()
        while True:
            ch = self.stdscr.getch()
            if ch == ord('Q'):
                raise SystemExit
            elif ch == ord('n') or ch == ord('N'):
                self.display()
                return
            elif ch == ord('W') or ch == ord('w'):
                self.write_file()
                raise SystemExit
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
    def handle_home_key(self):
        current_window = self.windows[self.context_window]
        current_window["col_num"] = 0
        self.mode = 'edit'
    def handle_end_key(self):
        current_window = self.windows[self.context_window]
        current_window["col_num"] = len(current_window["text"][current_window["line_num"]])
        self.mode = 'edit '
    def handle_ctrl_a(self):
        self.context_window = 1 - self.context_window
        if self.context_window == 1:
            self.mode = 'commd'
        else:
            self.mode = 'edit'
    def handle_ctrl_e(self):
            self.status = "execu"
            self.display()
            try:
                result = subprocess.run(
                    ['python', self.revision_manager.original_filename],
                    stdout=subprocess.PIPE, stderr=subprocess.PIPE, text=True
                )
                stdout_lines = result.stdout.split('\n')
                stderr_lines = result.stderr.split('\n')
                self.windows[1]['text'].append("Execution Results:")
                self.windows[1]['text'].append("stdout:")
                self.windows[1]['text'].extend(stdout_lines)
                self.windows[1]['text'].append("stderr:")
                self.windows[1]['text'].extend(stderr_lines)
            except subprocess.CalledProcessError as e:
                self.windows[1]['text'].append(f"Called Process Error:\n{str(e)}")
            except Exception as e:
                self.windows[1]['text'].append(f"Error:\n{str(e)}")
            self.adjust_window_offset()
            self.display()
    def handle_ctrl_t(self):
        self.status = "Ctrlt"
        self.display()
    def handle_ctrl_m(self):
        self.mode = "not captured ctrl-m"
    def handle_ctrl_q(self):
        self.mode = "not captured ctrl-q"
    def handle_ctrl_h(self):
        self.status = "CtrlH"
        self.display()
    def handle_ctrl_g(self):
            self.show_left_column = not self.show_left_column
            self.status = "bell"
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
            "Ctrl-V: Switch AI Viewpoint, E.g. Spelling, Grammar, Python Coder.",
            "Ctrl-W: Write the editor window to a file.",
            "Ctrl-R: Read the file to edit.",
            "Backslash key (\\): Quick Key AI Viewpoint Query.  Just key the backslash.",
            "Backspace key (<-): Toggle between the AI Viewpoint and the original, for quick comparison.",
            "Ctrl-D: Delete a line.",
            "Ctrl-X: Extract and mark lines (repeat Ctrl-X).",
            "Ctrl-Y: Yank (copy) the marked lines.",
            "Ctrl-P: Paste the yanked lines.",
            "Ctrl-K: If you need a backslash.",
            "Use the arrow keys to navigate.",
            "",
            "Try:",
            #"Crtl-A to switch to the AI command window,",
            "Type: 'Write a script that prints the Fibonacci series up to 89 inclusive.'",
            "Crtl-V to change viewpoint to Spelling.",
            "Depress the \\ key to fix spelling, inline, in the AI command window,",
            "Crtl-V to change viewpoint to Python Coder.",
            "Be sure to Ctrl-A back to the editor window,",
            "Press the \\ key to send your request to AI.",
            "Crtl-E to execute your code.",
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



