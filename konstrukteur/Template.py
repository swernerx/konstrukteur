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

htmlChars = re.compile("/[&<>\"\']")
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


    def render(self, data, partials, labels):
        """
        {String} Public render method which transforms the stored template text using the @data {Map},
        runtime specific @partials {Map?null} and @labels {Map?null}.
        """

        try:
            return self.__render(data, partials, labels);
        except:
            Console.error("Unable to render template " + (self.__name or ""));
            throw ex;


    def __variable(self, key, method, data):
        """
        {String} Outputs the @key {String} of @data {Map}
        using the given accessor @method {Integer} as HTML escaped variable.
        """

        value = accessor[method](key, data);
        if value is None:
            return ""

        return htmlChars.sub(str(value), htmlEscape)


    def __data(self, key, method, data, escape):
        """
        {String} Outputs the @key {String} of @data {Map}
        using the given accessor @method {Integer} as raw data.
        """

        value = accessor[method](key, data);
        if value is None:
            return ""

        return str(value)


    def __partial(self, name, data, partials, labels):
        """
        {String} Tries to find a partial in the current scope and render it
        """

        if partials and name on partials:
            return partials[name].__render(data, partials, labels);

        Console.warn("Could not find partial: " + name);
        return "";


    def __label(self, name, data, partials, labels):
        """
        {String} Tries to find a dynamic label by its @name {String} and renders
        the resulting label text like a partial template with the current
        @data {var}, defined @partials {Map} and other @labels {Map}.
        """

        text = None
        if labels is not None and name in labels:
            text = labels[name]

        if not text:
            return ""

        compiledLabel = TemplateCompiler.compile(text)
        return compiledLabel.__render(data, partials, labels)


    def __section(self, key, method, data, partials, labels, section):
        """
        Renders a section using the given @data {var}, user
        defined @partials {Map} and @labels {Map} and a @section {Function} specific renderer.
        """

        value = accessor[method](key, data);
        if value is not None:
            if type(value) is list:
                for pos, entry in enumerate(value):
                    section(self, value[pos], partials, labels)
            else:
                section(self, value, partials, labels)


    def __has(self, key, method, data):
        """
        {Boolean} Whether the given @key {String} has valid content inside @data {Map}
        using the given accessor @method {Integer}.
        """

        return bool(accessor[method](key, data))
