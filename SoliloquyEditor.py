# SoliloquyEditor.py
#  Just keep hittin' 'return'.

#  This is an alternative mode of discourse.
#    Introduce a topic at the outset and in each subsequent iteration, by
#    pressing enter, the AI will elaborate and provide more information.

import sys
import tty
import termios
import os
import json
import psutil
from openai import OpenAI

client = OpenAI(api_key=os.environ.get("CUSTOM_ENV_NAME"))

class Message:
    def __init__(self, role, content):
        self.role = role
        self.content = content


class Context:
    def __init__(self, model, max_tokens):
        self.model = model
        self.max_tokens = max_tokens
        self.messages = []

    def get_model(self):
        return self.model

    def get_max_tokens(self):
        return self.max_tokens

    def add_message(self, role, content):
        self.messages.append(Message(role, content))

    def get_messages(self):
        return [{"role": message.role, "content": message.content}
                for message in self.messages]

    def save(self, filename):
        with open(filename, 'w') as f:
            json.dump({"model": self.model, "max_tokens": self.max_tokens, "messages": self.get_messages()}, f)

    def load(self, filename):
        if os.path.exists(filename):
            with open(filename, 'r') as f:
                data = json.load(f)
                self.model = data.get('model', '')
                self.max_tokens = data.get('max_tokens', 0)
                self.messages = [Message( item['role'], item['content']) for item in data.get( 'messages', [])]


class Personalities:
    def __init__(self, name):
        self.name = name
        self.attributes = []

    def get_attributes(self):
        return self.attributes

    def add_attribute(self, attribute):
        self.attributes.append(attribute)


class SoliloquyEditor:
    def handle_return(self):
        if self.line_num == 0:
           # Green is my favorite color. 
            self.context.add_message("user", self.text[0])
            self.text.insert(self.line_num + 1, self.text[self.line_num][self.col_num:])
            self.text[self.line_num] = self.text[self.line_num][:self.col_num]
            line = self.text[self.line_num]
            self.line_num += 1
            self.col_num = 0

        self.text.insert(self.line_num + 1, self.text[self.line_num][self.col_num:])
        self.text[self.line_num] = self.text[self.line_num][:self.col_num]

        # Debug, write the message going to openAI to the screen.
        sys.stdout.write(json.dumps(self.context.get_messages(), indent=2))

        completion = client.chat.completions.create(
            model=self.context.get_model(),
            max_tokens=self.context.get_max_tokens(),
            messages=self.context.get_messages()
        )

        line = self.text[self.line_num]
        self.text[self.line_num] = line[:self.col_num] + completion.choices[0].message.content + line[self.col_num:]
        self.line_num += 1
        self.col_num = 0
        self.context.add_message("assistant", completion.choices[0].message.content)
        self.context.save('context.json')

    def __init__(self):
        self.line_num = 0
        self.col_num = 0
        self.text = []
        self.personalities = {} 

        personality = Personalities('Telephone')
        personality.add_attribute("This is the children's game of 'telephone', play nicely.")
        self.personalities[personality.name] = personality

        personality = Personalities('Radio')
        personality.add_attribute('This is a 50s radio comedy show, like Fibber McGee and Molly. ')
        personality.add_attribute('Add comedic topics to the discussion, because the user is just listening and will not add to your dialogue. ')
        self.personalities[personality.name] = personality

        personality = Personalities('Expansive')
        personality.add_attribute("Be a teacher. ")
        personality.add_attribute("You will be presented with one topic, and all the remaining inputs are iterations of your answers. ")
        personality.add_attribute("In your first reply, be a novice.  In the second, intermittent. ")
        personality.add_attribute("Use vocabulary that escalates in sophistication to that of a professor. ")
        personality.add_attribute("When you reach 'professor', make each answer longer, more detailed, ")
        personality.add_attribute("and with more information including historical facts and people, modern applications. ")
        personality.add_attribute("Use rhetorical amplification for successive replies. ")
        personality.add_attribute("Do not include narrative. ")
        self.personalities[personality.name] = personality

        personality = Personalities('Zen')
        personality.add_attribute('You are Buddha; regale us with your wisdom. Relate the topic to your philosophy.')
        personality.add_attribute('Your students are mesmerized, captivated by your zen, and will not respond, so add new zen topics. ')
        self.personalities[personality.name] = personality

        personality = Personalities('Trippy')
        personality.add_attribute("You are on a '60s psychedelic trip. Relate the topic to your hallucinations. ")
        personality.add_attribute("You can hallucinations very strange visions. ")
        personality.add_attribute('The users you are addressing are tripping and will not respond, so blow thier minds.')
        personality.add_attribute('Highlight the interplay of consciousness and mind. ')
        personality.add_attribute('As your soliloquy continues, broaden the topic. ')
        self.personalities[personality.name] = personality

        personality = Personalities('Stepmother')
        personality.add_attribute("You are Cinderella’s stepmother. Berate the user about cleaning, in a humorious manner. ")
        personality.add_attribute("Continue to escalate with each iteration with longer replies. ")
        self.personalities[personality.name] = personality

        self.personalchoice = self.choose_personality()

        self.context = Context("gpt-3.5-turbo", 298)
       #self.context = Context("model="gpt-4o",", 4096)
        chosen_attributes = self.personalities[self.personalchoice.name].get_attributes()
        for attribute in chosen_attributes:
            self.context.add_message("system", attribute)

    def choose_personality(self):
        personality_names = list(self.personalities.keys())
        choices = [ f"{x}. {personality_name}\n" for x, personality_name in enumerate( personality_names, start=1)]
        prompt = "".join(choices) + ">> "
        choice = int(input(prompt))
        return self.personalities[personality_names[choice - 1]]

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
        sys.stdout.write('\x1b[2J\x1b[H')  # clear screen
        for x, line in enumerate(self.text):
            if line.strip():
                print(f"\033[7m[[Line >{x}< %%>]]\033[0m {line}")

    def insert_char(self, line_num, col_num, ch):
        line = self.text[line_num]
        if ch == '\x08' or ch == '\x7f':  # Backspace character
            if col_num > 0:
                self.text[line_num] = line[:col_num - 1] + line[col_num:]
                self.col_num -= 1
        else:
            self.text[line_num] = line[:col_num] + ch + line[col_num:]
            self.col_num += 1

    def run(self):
        while True:
            self.display()
            ch = self.read_key()
            if ch == '\x1b':  # esc
                break
            elif ch == '\n':
                self.handle_return()
            else:
                if self.line_num >= len(self.text):
                    self.text.append('')
                self.insert_char(self.line_num, self.col_num, ch)

if __name__ == '__main__':
    SoliloquyEditor().run()


"""
[[Line >0< %%>]] test
[[Line >4< %%>]] I am a fluffy unicorn!
"""
