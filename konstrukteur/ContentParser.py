#
# Konstrukteur - Static Site Generator
# Copyright 2013-2014 Sebastian Fastner
# Copyright 2014 Sebastian Werner
#

import glob
import os
import sys
import dateutil

import jasy.core.Console as Console
import jasy.core.File as File

import konstrukteur.Language
import konstrukteur.Util as Util
import konstrukteur.MarkdownParser

class ContentParser:

    """Content parser class for Konstrukteur."""

    def __init__(self, extensions, defaultLanguage="en"):
        self.__extensions = extensions
        self.__extensionParser = {
            "html" : konstrukteur.HtmlParser,
            "markdown" : konstrukteur.MarkdownParser,
            "md" : konstrukteur.MarkdownParser,
            "txt" : konstrukteur.MarkdownParser
        }

        self.__id = 1
        self.__languages = set()
        self.__defaultLanguage = defaultLanguage


    def getLanguages(self):
        return self.__languages


    def parse(self, path):
        Console.info("Processing %s..." % path)
        Console.indent()

        collection = []
        for extension in self.__extensions:
            for filename in glob.iglob(os.path.join(path, "*.%s" % extension)):
                basename = os.path.basename(filename)
                Console.debug("Parsing %s" % basename)

                parsed = self.__delegatedParse(filename, extension)
                if not parsed:
                    Console.error("Error parsing file %s" % filename)
                    continue

                self.__postProcess(parsed, filename)
                collection.append(parsed)

        Console.info("Registered %s files.", len(collection))
        Console.outdent()

        return collection


    def __postProcess(self, parsed, filename):
        if "slug" in parsed:
            parsed["slug"] = Util.fixSlug(parsed["slug"])
        else:
            parsed["slug"] = Util.fixSlug(parsed["title"])

        if not "status" in parsed:
            parsed["status"] = "published"

        # Expect default language when not defined otherwise
        if not "lang" in parsed:
            parsed["lang"] = self.__defaultLanguage

        # Add modification time and short hash
        parsed["mtime"] = os.path.getmtime(filename)
        parsed["hash"] = File.sha1(filename)[0:8]

        # Create simple boolean flag for publish state check
        parsed["isPublished"] = parsed["status"] == "published"

        # Parse date to a date instance and pre-formatted date strings
        if "date" in parsed:
            parsed["date"] = dateutil.parser.parse(parsed["date"]).replace(tzinfo=dateutil.tz.tzlocal())
            parsed["date-daily"] = parsed["date"].strftime("%y-%m-%d")
            parsed["date-monthly"] = parsed["date"].strftime("%y-%m")

        # Automatically register new languages
        self.__languages.add(parsed["lang"])

        return parsed


    def __delegatedParse(self, filename, extension):
        """Parse single content file."""

        if not extension in self.__extensionParser:
            raise RuntimeError("No parser for extension %s registered!" % extension)

        # Delegate to main parser
        return self.__extensionParser[extension].parse(filename)
