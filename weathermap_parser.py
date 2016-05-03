from collections import defaultdict
from re import compile as re_compile

class WeathermapParser:
    RE_LINE = re_compile(r'^(?P<indent>\s*)(?P<command>[A-Z0-9]+)\s(?P<parameters>.*)$')

    def load(self, filename = 'example-header.conf'):
        with open(filename) as headerfile:
            template = defaultdict(dict)
            previous_object = ''
            previous_section = ''

            for line in headerfile:
                is_command = self.RE_LINE.match(line)
                if is_command:
                    groups = is_command.groupdict()

                    command = groups['command']
                    parameters = groups['parameters'].strip()
                    object_data = "%s %s" % (command, parameters)

                    if not groups['indent']: # New object, just add to tree
                        object_type = object_data.split(' ', 1)[0]

                        section = '%sS' % object_type
                        if object_type not in ('NODE', 'LINK'):
                            section = 'GLOBALS'

                        previous_object = object
                        previous_section = section

                        template[section][object] = {}

                    else: # extra parameters for previous object
                        template[previous_section][previous_object][command] = parameters
            return template
        return False


    def render(self, data, indent=0):
        result = ''
        for k, v in sorted(data.iteritems()):
            if isinstance(v, dict) and len(v) > 0:
                result += "%s\n" % k
                result += "%s\n" % self.render(v, indent+1)
            else:
                result += "%s%s" % ('    '*indent, k)
                if len(v) > 0:
                    result += " %s" % (v)
                result += "\n"
        return result


    def dump(self, data):
        s = ''
        s += self.render(data['GLOBALS'])
        s += self.render(data['NODES'])
        s += self.render(data['LINKS'])
        return s
