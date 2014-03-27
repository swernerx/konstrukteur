# ==================================================================================================
#   Core - JavaScript Foundation
#   Copyright 2010-2012 Zynga Inc.
#   Copyright 2012-2014 Sebastian Werner
# --------------------------------------------------------------------------------------------------
#   Based on the work of:
#   Hogan.JS by Twitter, Inc.
#   https://github.com/twitter/hogan.js
#   Licensed under the Apache License, Version 2.0
#   http://www.apache.org/licenses/LICENSE-2.0
# ==================================================================================================

import re

hasOwnProperty = Object.prototype.hasOwnProperty;
undef = None

htmlChars = re.compile("/[&<>\"\']", "g");
htmlMap = {
    '&': '&amp;',
    '<': '&lt;',
    '>': '&gt;',
    "'": '&#39;',
    '"': '&quot;'
}

def htmlEscape(str):
    return htmlMap[str]

def getter(key, obj):
    if type(obj) is dict:
        camelized = core.String.camelize(key);
        if camelized in obj:
            return obj[camelized]

def plain(key, data):
    if data is not None:
        return data

def structure(key, data):
    splits = key.split(".");
    for split in splits:
        data = getter(split, data);
        if data is None:
            return None

    return data

accessor = {
    "2": plain,
    "1": structured,
    "0": getter
}


#
# This is the template class which is typically initialized and
# configured using the {TemplateCompiler#compile} method.
#
class Template:

    __name = None
    __text = None
    __render = None


    #
    # Creates a template instance with the given @render {Function} method. Best way to work with
    # the template class is to create one using the {core.template.Compiler#compile} method.
    #
    def __init__(self, render, text, name):
        self.__render = render;
        self.__text = text;
        self.__name = name;

        #
        # {String} Public render method which transforms the stored template text using the @data {Map},
        # runtime specific @partials {Map?null} and @labels {Map?null}.
        #
        def render(self, data, partials, labels):

            try:
                return self.__render(data, partials, labels);
            except:
                Console.error("Unable to render template " + (self.__name||""));
                throw ex;


        #
        # {String} Outputs the @key {String} of @data {Map}
        # using the given accessor @method {Integer} as HTML escaped variable.
        #
        def __variable(self, key, method, data):
            var value = accessor[method](key, data);
            var str = value == null ? "" : "" + value;

            return str.replace(htmlChars, htmlEscape);


        #
        # {String} Outputs the @key {String} of @data {Map}
        # using the given accessor @method {Integer} as raw data.
        #
        def __data(self, key, method, data, escape):
            var value = accessor[method](key, data);
            return value == null ? "" : "" + value;


        #
        # {String} Tries to find a partial in the current scope and render it
        #
        def __partial(self, name, data, partials, labels):

            if (partials && hasOwnProperty.call(partials, name))
            {
                return partials[name].__render(data, partials, labels);
            }
            else
            {
                if (jasy.Env.isSet("debug")) {
                    self.warn("Could not find partial: " + name);
                }

                return "";
            }


        #
        # {String} Tries to find a dynamic label by its @name {String} and renders
        # the resulting label text like a partial template with the current
        # @data {var}, defined @partials {Map} and other @labels {Map}.
        #
        def __label(self, name, data, partials, labels):
            var text = labels && labels[name];
            if (text == null) {
                return "";
            }

            // Automatically execute dynamic labels e.g. trn() with plural strings
            if (typeof text == "function") {
                text = text();
            }

            var compiledLabel = core.template.Compiler.compile(text);
            return compiledLabel.__render(data, partials, labels);


        #
        # Renders a section using the given @data {var}, user
        # defined @partials {Map} and @labels {Map} and a @section {Function} specific renderer.
        #
        def __section(self, key, method, data, partials, labels, section):

            value = accessor[method](key, data);
            if value != undef:

                // Auto cast
                if (value.toArray) {
                    value = value.toArray();
                }

                if (value instanceof Array)
                {
                    for (var i=0, l=value.length; i<l; i++) {
                        section.call(this, value[i], partials, labels);
                    }
                }
                else
                {
                    section.call(this, value, partials, labels);
                }


        #
        # {Boolean} Whether the given @key {String} has valid content inside @data {Map}
        # using the given accessor @method {Integer}.
        #
        def _has(self, key, method, data):

            value = accessor[method](key, data)

            if (value instanceof Array) {
                return value.length > 0;
            } else if (value != null && value.isEmpty) {
                return !value.isEmpty();
            } else {
                return value === '' || !!value
            }
