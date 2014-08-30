#
# Konstrukteur - Static Site Generator
# Copyright 2013-2014 Sebastian Fastner
# Copyright 2014 Sebastian Werner
#

import glob
import os
import sys
import dateutil
import re

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
        self.__alternateLanguages = {}
        self.__fileNameLanguage = re.compile(r"^(.*)\.([a-z]{2})\.[a-zA-Z]+$")


    def getLanguages(self):
        return self.__languages


    def parse(self, path, namespace):
        Console.info("Processing %s..." % path)
        Console.indent()

        collection = []
        for extension in self.__extensions:
            for fileName in glob.iglob(os.path.join(path, "*.%s" % extension)):

                # Extract fileId and fileLanguage from file name
                relativeFileName = os.path.relpath(fileName, path)
                languageMatch = self.__fileNameLanguage.match(relativeFileName)
                if languageMatch:
                    fileId = languageMatch.group(1)
                    fileLanguage = languageMatch.group(2)
                else:
                    fileId = os.path.splitext(relativeFileName)[0]
                    fileLanguage = None

                fileId = namespace + "." + fileId.replace(os.sep, ".")
                Console.debug("Parsing %s...", fileId)

                # Custom parser support
                model = self.__delegatedParse(fileName, extension)
                if not model:
                    Console.error("Error parsing file %s" % fileName)
                    continue

                # Add missing language / id data
                if not "id" in model:
                    model["id"] = fileId
                if not "language" in model:
                    model["language"] = fileLanguage or self.__defaultLanguage
                elif fileLanguage and fileLanguage != model["language"]:
                    raise Exception("Different language definitions at file name / file content level in: %s" % fileName)

                # Cleanup and extend model data
                self.__postProcess(model, fileName)

                # Track alternate languages
                alternates = self.__alternateLanguages
                if not fileId in alternates:
                    alternates[fileId] = {}
                elif fileLanguage in alternates[fileId]:
                    raise Exception("Got conflict. Using same fileID (%s) and language (%s) like previously processed item!" % (fileId, fileLanguage))

                alternates[fileId][fileLanguage] = model

                # Automatically track all used languages
                self.__languages.add(model["language"])

                # Register all item models
                collection.append(model)

        Console.info("Registered %s files.", len(collection))
        Console.outdent()

        return collection


    def __postProcess(self, model, fileName):
        # Parse/Normalize slug
        if "slug" in model:
            model["slug"] = Util.fixSlug(model["slug"])
        else:
            model["slug"] = Util.fixSlug(model["title"])

        # Support for drafts
        if not "status" in model:
            model["status"] = "published"

        model["isPublished"] = model["status"] == "published"

        # Add modification time and short hash
        model["mtime"] = os.path.getmtime(fileName)
        model["hash"] = File.sha1(fileName)[0:8]

        # Parse date to a date instance and pre-formatted date strings
        if "date" in model:
            model["date"] = dateutil.parser.parse(model["date"]).replace(tzinfo=dateutil.tz.tzlocal())
            model["date-daily"] = model["date"].strftime("%y-%m-%d")
            model["date-monthly"] = model["date"].strftime("%y-%m")

        return model


    def __delegatedParse(self, filename, extension):
        """Parse single content file."""

        if not extension in self.__extensionParser:
            raise RuntimeError("No parser for extension %s registered!" % extension)

        # Delegate to main parser
        return self.__extensionParser[extension].parse(filename)
