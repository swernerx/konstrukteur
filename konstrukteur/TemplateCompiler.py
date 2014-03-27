#
# Jasy - Web Tooling Framework
# Copyright 2010-2012 Zynga Inc.
# Copyright 2013-2014 Sebastian Fastner
#
# Based upon
# Core - JavaScript Foundation
# Copyright 2010-2012 Zynga Inc.
# Copyright 2012-2014 Sebastian Werner
#
# Based upon
# Hogan.JS by Twitter, Inc.
# https://github.com/twitter/hogan.js
# Licensed under the Apache License, Version 2.0
#

__all__ = ["compile"]

import jasy.template.Parser as Parser
import konstrukteur.Template as Template

accessTags = [
    "#",     # go into section / loop start
    "?",     # if / has
    "^",     # if not / has not
    "$",     # insert variable
    "="      # insert raw / non escaped
]

# Tags which support children
innerTags = [
    "#",
    "?",
    "^"
]

indentString = "  "
innerCounter = 0

def escapeContent(content):
    return content.replace("\"", "\\\"").replace("\n", "\\n")


def escapeMatcher(str):
    return str.replace("\\", "\\\\").replace("\"", "\\\"").replace("\n", "\\\n").replace("\r", "\\\r")


def walk(node, labels, nostrip, indent):
    global innerCounter

    code = ""
    prefix = indent * indentString

    for current in node:
        if type(current) == str:
            code += prefix + 'buf += "' + escapeMatcher(current) + '"\n'
        elif current["tag"] == "\n":
            code += prefix + 'buf += "\\n"\n'
        else:
            tag = current["tag"]
            name = current["name"]
            escaped = escapeMatcher(name)

            if tag in accessTags:
                if name == ".":
                    accessor = 2
                elif "." in name:
                    accessor = 1
                else:
                    accessor = 0

                accessorCode = '"' + escaped + '",' + str(accessor) + ',data'

                if tag in innerTags:
                    innerCode = walk(current["nodes"], labels, nostrip, indent+1)

                if tag == "?":
                    code += prefix + 'if self.__has(' + accessorCode + '):\n' + innerCode + '\n'
                elif tag == "^":
                    code += prefix + 'if not self.__has(' + accessorCode + '):\n' + innerCode + '\n'
                elif tag == "#":
                    innerCounter += 1
                    code += prefix + ('def inner%s(self, data, partials, labels):\n' % innerCounter) + innerCode + '\n'
                    code += prefix + 'self.__section(' + accessorCode + ', partials, labels, inner%s)\n' % innerCounter
                elif tag == "=":
                    code += prefix + 'buf += self.__data(' + accessorCode + ')\n'
                elif tag == "$":
                    code += prefix + 'buf += self.__variable(' + accessorCode + ')\n';

            elif tag == ">":
                code += prefix + 'buf += self.__partial("' + escaped + '",data, partials, labels)\n'
            elif tag == "_":
                if labels and escaped in labels:
                    code += walk(Parser.parse(labels[escaped], True), labels, indent+1);
                else:
                    code += prefix + 'buf += self.__label("' + escaped + '", data, partials, labels)\n'

    return code


def compile(text, labels=[], nostrip=False, name=None):
    # Parse text into a tree
    tree = Parser.parse(text, nostrip)

    # Generate code for render function
    wrapped = indentString + 'buf = ""\n' + walk(tree, labels, nostrip, 1) + "\n" + indentString + 'return buf'
    code = "def render(self, data, partials, labels):\n%s" % wrapped

    # Execute in an sandboxes environment
    export = {}
    exec(code, None, export)

    # Create new template instance based on "compiled" exported render method
    return Template.Template(export["render"], text, name)
