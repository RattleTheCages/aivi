# QuickSpellEditor.py

# Press the backslash key, located above the Enter key, to correct the spelling and grammar inline.
# If you don’t like the corrections, you can press the backspace key, of course, which is located above the backslash key.
# The backslash key sends the text to the AI for grammar correction.
# You can quickly toggle between the AI’s correction suggestions and your original text by pressing the backspace key, allowing for easy comparison.

import sys
import tty
import termios
import os
import argparse
import json
import psutil
from openai import OpenAI
client = OpenAI(api_key=os.environ.get("CUSTOM_ENV_NAME"))

parser = argparse.ArgumentParser()
parser.add_argument('--file', default='quick.txt')
args = parser.parse_args()

class CogQuery:
    def __init__(self, role, content):
        self.role = role
        self.content = content

class Cogtext:
    def __init__(self, model, max_tokens):
        self.model = model
        self.max_tokens = max_tokens
        self.cogessages = []
        self.usermsg = []

    def reset(self):
        self.cogessages = [msg for msg in self.cogessages if msg.role == 'system']
        self.usermsg = []

    def get_model(self):
        return self.model

    def get_maxtokens(self):
        return self.max_tokens

    def add_cogtext(self, role, content):
        self.cogessages.append(CogQuery(role, content))

    def get_cogtext(self):
        context =  [{"role": message.role, "content": message.content}
                for message in self.cogessages]
        context +=  [{"role": "user", "content": umsg}
                for umsg in self.usermsg]
        return context

    def add_usermsg(self, msg):
        self.usermsg.append(msg)

    def save_cogtext(self, filename):
        with open(filename, 'w') as f:
            json.dump({"model": self.model, "max_tokens": self.max_tokens, "messages": self.get_cogtext()}, f)

    def load_cogtext(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                self.model = data.get('model', '')
                self.max_tokens = data.get('max_tokens', 0)
                self.cogessages = [CogQuery( item['role'], item['content']) for item in data.get( 'messages', [])]

class Cognatlities:
    def __init__(self, name):
        self.name = name
        self.attributes = []

    def get_attributes(self):
        return self.attributes

    def add_attribute(self, attribute):
        self.attributes.append(attribute)

class QuickSpellEditor:
    def handle_return(self):
        line = self.text[self.line_num]
        self.context.add_cogtext("user", line)
        self.context.add_usermsg(line)
        self.text.insert(self.line_num + 1, self.text[self.line_num][self.col_num:])
        self.text[self.line_num] = self.text[self.line_num][:self.col_num]

        line = self.text[self.line_num]
        self.text[self.line_num] = line[:self.col_num] + '' + line[self.col_num:]
        self.line_num += 1
        self.col_num = 0
        self.linesInContext += 1

    def __init__(self):
        self.mode = "edit"
        self.status = ""
        self.line_num = 0
        self.linesInContext = 0
        self.text = []
        self.col_num = 1
        self.oldtext = []

        cognatlity = Cognatlities('Spell and Grammer check')
        cognatlity.add_attribute('Your task is to spell and grammer check the following sentences. ')
        cognatlity.add_attribute('Take each sentence and output a corresponding corrected sentence. ')
        cognatlity.add_attribute('The user wants the answer strictly formatted as the quesiton. ')

        self.context = Cogtext("gpt-3.5-turbo", 298)
       #self.context = Cogtext("model="gpt-4o",", 4096)
        chosen_attributes = cognatlity.get_attributes()
        for attribute in chosen_attributes:
            self.context.add_cogtext("system", attribute)

    def read_key(self):
        fd = sys.stdin.fileno()
        old_settings = termios.tcgetattr(fd)
        try:
            tty.setcbreak(sys.stdin.fileno())
            ch = sys.stdin.read(1)
        finally:
            termios.tcsetattr(fd, termios.TCSADRAIN, old_settings)
        return ch

    def display(self):
        modeOrStatus = self.mode
        if self.status != "":
            modeOrStatus = self.status
            self.status = ""
        sys.stdout.write('\x1b[2J\x1b[H')  # clear screen
        for y, line in enumerate(self.text):
            print(f"\033[7m>{y:03}<{modeOrStatus:5}>\033[0m ", end="")
            if y == self.line_num:
                for x, ch in enumerate(line, start=1):
                    if x == self.col_num:
                        print('\033[7m' + ch + '\033[0m', end='')
                    else:
                        print(ch, end='')
                print()
            else:
                print(line)

    def insert_char(self, line_num, col_num, ch):
        self.mode = 'edit'
        line = self.text[line_num]
        if ch == '\x08' or ch == '\x7f':  # Backspace character
            if col_num > 0:
                self.text[line_num] = line[:col_num - 1] + line[col_num:]
                self.col_num -= 1
        else:
            self.text[line_num] = line[:col_num] + ch + line[col_num:]
            self.col_num += 1

    def handle_up_arrow(self):
        if self.line_num > 0:
            self.mode = "edit"
            self.line_num -= 1
            if self.col_num > len(self.text[self.line_num]):
                self.col_num = len(self.text[self.line_num])

    def handle_down_arrow(self):
        if self.line_num < self.linesInContext:
            self.mode = "edit"
            self.line_num += 1
            if self.col_num > len(self.text[self.line_num]):
                self.col_num = len(self.text[self.line_num])

    def handle_right_arrow(self):
        line = self.text[self.line_num]
        if self.col_num < len(line):
            self.mode = "edit"
            self.col_num += 1

    def handle_left_arrow(self):
        if self.col_num > 0:
            self.mode = "edit"
            self.col_num -= 1

    def handle_backspace(self, ch):
        if self.mode == "reply" or self.mode == 'undo':
            if self.mode == 'reply':
                self.mode = 'undo'
            else:
                self.mode = 'reply'

            self.oldertext = self.text
            self.text = self.oldtext
            self.oldtext = self.oldertext
        else:
            self.insert_char(self.line_num, self.col_num, ch)

    def handle_backslash(self):
      # Light green is my favorite color, but the sky is a wonderful hue of blue.
        self.context.reset()
        userlines = ""
        for line in self.text:
            userlines += line + '\n'
        self.context.add_usermsg(userlines)

        completion = client.chat.completions.create(
            model=self.context.get_model(),
            max_tokens=self.context.get_maxtokens(),
            messages=self.context.get_cogtext()
        )
        self.context.add_cogtext("assistant", completion.choices[0].message.content)
        self.context.save_cogtext('context.json')

        # Debug, write the context with the AI reply.
        #sys.stdout.write(json.dumps(self.context.get_cogtext(), indent=2))

        self.oldtext = self.text
        self.text = []
        self.line_num = 0
        self.mode = "reply"

        content_lines = completion.choices[0].message.content.split('\n')
        for cline in content_lines:
            self.text.insert(self.line_num, cline)
            self.line_num += 1
            sys.stdout.write(cline)

        self.line_num -= 1
        self.linesInContext = self.line_num
        self.col_num = len(self.text[self.line_num])

    def write_file(self):
        try:
            with open(args.file, 'w') as f:
                for line in self.text:
                    f.write(line + '\n')
            self.status = "wrote"
        except Exception as e:
            self.status = "no wri"

    def read_file(self):
        try:
            with open(args.file, 'r') as f:
                self.text = [line.rstrip('\n') for line in f]
            self.status = "wrote"
        except FileNotFoundError:
            self.status = "not f"

    def run(self):
        self.text.append('')
        while True:
            self.display()
            ch = self.read_key()
            if ch == '\x03':  # Ctrl-C
                break
            elif ch == '\x1b':  # Esc
                next_ch = self.read_key()
                if next_ch == '[':  # Bracket
                    next_ch = self.read_key()
                    if next_ch == 'A':  # Up arrow
                        self.handle_up_arrow()
                    elif next_ch == 'B':  # Down arrow
                        self.handle_down_arrow()
                    if next_ch == 'C':  # Up arrow
                        self.handle_right_arrow()
                    elif next_ch == 'D':  # Down arrow
                        self.handle_left_arrow()
            elif ch == '\\':  # Backslash
                self.handle_backslash()
            elif ch == '\n':  # Return
                self.handle_return()
            elif ch == '\x08' or ch == '\x7f':  # Backspace
                self.handle_backspace(ch)
            elif ch == '\x17':  # Ctrl-W
                self.write_file()
            elif ch == '\x12':  # Ctrl-R
                self.read_file()
            else:
                if self.line_num >= len(self.text):
                    self.text.append('')
                self.insert_char(self.line_num, self.col_num, ch)

if __name__ == '__main__':
    QuickSpellEditor().run()

