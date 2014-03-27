#
# Konstrukteur - Static Site Generator
# Copyright 2013-2014 Sebastian Fastner
# Copyright 2014 Sebastian Werner
#

# Little helper to allow python modules in libs path
import sys, os.path, inspect, json
filename = inspect.getframeinfo(inspect.currentframe()).filename
path = os.path.join(os.path.dirname(os.path.abspath(filename)), "..", "konstrukteurlibs", "watchdog", "src")
sys.path.insert(0,path)


__all__ = ["build"]

import re
import os.path
import dateutil.parser
import dateutil.tz
import datetime
import time
import pystache
import itertools

from jasy.env.State import session

import jasy.core.Console as Console
import jasy.core.FileManager as FileManager
import jasy.core.Cache as Cache
import jasy.template.Parser as TemplateParser

from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

import konstrukteur.HtmlParser
import konstrukteur.HtmlBeautifier
import konstrukteur.Language
import konstrukteur.FileWatcher
import konstrukteur.ContentParser
import konstrukteur.Util


import konstrukteur.TemplateCompiler as TemplateCompiler





COMMAND_REGEX = re.compile(r"{{@(?P<cmd>\S+?)(?:\s+?(?P<params>.+?))}}")

class Konstrukteur:
	""" Core application class for Konstrukteur """

	sitename = None
	siteurl = None
	posturl = None
	pageurl = None
	feedurl = None
	extensions = None
	theme = None
	defaultLanguage = None
	config = None

	__regenerate = False
	__templates = None
	__pages = None
	__languages = None

	__postUrl = None
	__pageUrl = None
	__feedUrl = None

	__renderer = None
	__safeRenderer = None
	__fileManager = None
	__locale = None


	def __init__(self, profile, regenerate=False, project=None):
		# Figuring out main project
		session = profile.getSession()
		main = project or session.getMain()

		self.__profile = profile
		self.__session = session
		self.__locale = {}
		self.__commandReplacer = []
		self.__id = 0
		self.__regenerate = not regenerate == False
		self.__cache = main.getCache()

		# Importing configuration from project
		self.config = main.getConfigValue("konstrukteur")
		self.sitename = main.getConfigValue("konstrukteur.site.name", "Test website")
		self.siteurl = main.getConfigValue("konstrukteur.site.url", "//localhost")
		self.__postUrl = pystache.parse(main.getConfigValue("konstrukteur.blog.postUrl", "{{current.lang}}/blog/{{current.slug}}"))
		self.__pageUrl = pystache.parse(main.getConfigValue("konstrukteur.pageUrl", "{{current.lang}}/{{current.slug}}"))
		self.__feedUrl = pystache.parse(main.getConfigValue("konstrukteur.blog.feedUrl", "feed.{{current.lang}}.xml"))
		self.extensions = main.getConfigValue("konstrukteur.extensions", ["markdown", "html"])
		self.theme = main.getConfigValue("konstrukteur.theme", main.getName())
		self.defaultLanguage = main.getConfigValue("konstrukteur.defaultLanguage", "en")
		self.__fileManager = FileManager.FileManager(self.__profile)


	def build(self):
		""" Build static website """

		Console.info("Intializing Konstrukteur...")
		Console.indent()

		# Path configuration
		# TODO: Use Jasy configuration instead
		self.__templatePath = os.path.join("source", "template")
		self.__contentPath = os.path.join("source", "content")
		self.__sourcePath = os.path.join("source")

		if not os.path.exists(self.__templatePath):
			raise RuntimeError("Path to templates not found : %s" % self.__templatePath)
		if not os.path.exists(self.__contentPath):
			raise RuntimeError("Path to content not found : %s" % self.__contentPath)

		# A theme could be any project registered in the current session
		if self.theme:
			themeProject = session.getProjectByName(self.theme)
			if not themeProject:
				raise RuntimeError("Theme '%s' not found" % self.theme)

		self.__initializeTemplates()
		self.__generateOutput()

		# Start actual file watcher
		if self.__regenerate:
			# We need to pause the session for not blocking the cache
			self.__session.pause()

			fileChangeEventHandler = konstrukteur.FileWatcher.FileChangeEventHandler()

			observer = Observer()
			observer.schedule(fileChangeEventHandler, self.__sourcePath, recursive=True)
			observer.start()

			try:
				Console.info("Waiting for file changes (abort with CTRL-C)")
				while True:
					time.sleep(1)
					if fileChangeEventHandler.dirty:
						fileChangeEventHandler.dirty = False
						self.__generateOutput()
			except KeyboardInterrupt:
				observer.stop()

			observer.join()

			# Resume the session after exciting
			self.__session.resume()

		Console.outdent()


	def __generateOutput(self):
		""" Build static website """

		Console.info("Building website....")
		Console.indent()

		self.__parseContent()
		self.__outputContent()

		Console.info("Website successfully build!")


	def __fixJasyCommands(self, content):
		def commandReplacer(command):
			cmd = command.group("cmd")
			params = command.group("params").split()
			id = "jasy_command_%s" % self.__id

			self.__id += 1
			self.__commandReplacer.append((id, cmd, params))

			return "{{%s}}" % id

		return re.sub(COMMAND_REGEX, commandReplacer, content)


	def __fixTemplateName(self, name):
		s = name.split(".")
		sname = s[-1]
		sname = sname[0].upper() + sname[1:]
		return ".".join(s[:-1] + [sname])


	def __initializeTemplates(self):
		""" Process all templates to support jasy commands """

		# Build a map of all known templates
		self.__templates = {}
		for project in session.getProjects():
			templates = project.getItems("jasy.Template")
			if templates:
				for name, item in templates.items():
					self.__templates[name] = item.getText()


		for name in self.__templates:
			content = self.__templates[name]
			# tree = TemplateParser.parse(content)
			compiled = TemplateCompiler.compile(content)
			self.__templates[name] = compiled

		# Create two rendereres for different use cases
		self.__renderer = pystache.Renderer(partials=self.__templates, escape=lambda u: u)
		self.__safeRenderer = pystache.Renderer(partials=self.__templates)


	def __parseContent(self):
		""" Parse all content items in users content directory """

		contentParser = konstrukteur.ContentParser.ContentParser(self.extensions, self.__fixJasyCommands, self.defaultLanguage)
		self.__languages = []

		Console.info("Parsing content...")
		Console.indent()
		self.__pages = contentParser.parse(os.path.join(self.__contentPath, "page"), self.__languages)
		self.__posts = contentParser.parse(os.path.join(self.__contentPath, "post"), self.__languages)
		Console.outdent()

		Console.info("Processing locales...")
		Console.indent()
		for language in self.__languages:
			Console.info("Adding language: %s", language)
			if not language in self.__locale:
				self.__locale[language] = konstrukteur.Language.LocaleParser(language)
		Console.outdent()


	def __mapLanguages(self, languages, currentItem):
		""" Annotate languges list with information about current language """

		def languageMap(value):
			currentLanguage = value == currentItem["lang"]
			currentName = self.__locale[value].getName(value)

			if "translations" not in currentItem:
				return None

			if currentLanguage:
				translatedName = currentName
				relativeUrl = "."
			else:
				translatedName = self.__locale[currentItem["lang"]].getName(value)
				relativeUrl = currentItem["translations"][value]

			return {
				"code" : value,
				"current" : currentLanguage,
				"name" : currentName,
				"translatedName" : translatedName,
				"relativeUrl" : relativeUrl,
				"page" : currentItem
			}


		return list(map(languageMap, languages))



	def __refreshUrls(self, pages, currentItem, pageUrlTemplate):
		""" Refresh urls of every page relative to current active page """
		siteUrl = self.siteurl

		for pageItem in pages:
			url = pageItem["url"] if "url" in pageItem else self.__renderer.render(pageUrlTemplate, { "current" : pageItem })
			pageItem["absoluteUrl"] = os.path.join(siteUrl, url)
			pageItem["rootUrl"] = url
			pageItem["baseUrl"] = os.path.relpath("/", os.path.dirname("/%s" % url))

		for pageItem in pages:
			if pageItem == currentItem:
				pageItem["active"] = True
				pageItem["relativeUrl"] = ""
			else:
				pageItem["active"] = False
				pageItem["relativeUrl"] = os.path.relpath(pageItem["rootUrl"], os.path.dirname(currentItem["rootUrl"]))

		for pageItem in pages:
			if pageItem["slug"] == currentItem["slug"]:
				if not pageItem["lang"] == currentItem["lang"]:
					if not "translations" in currentItem:
						currentItem["translations"] = {}

					currentItem["translations"][pageItem["lang"]] = pageItem["relativeUrl"]



	def __filterAndSortPages(self, pages, currentItem):
		""" Return sorted list of only pages of same language and not hidden """
		pageList = []

		for pageItem in pages:
			if pageItem["lang"] == currentItem["lang"] and not pageItem["status"] == "hidden":
				pageList.append(pageItem)

		return sorted(pageList, key=lambda page: page["pos"])



	def __jasyCommandsHandling(self, renderModel, filename):
		oldWorkingPath = self.__profile.getWorkingPath()
		self.__profile.setWorkingPath(os.path.dirname(filename))

		for id, cmd, params in self.__commandReplacer:
			result, type = self.__profile.executeCommand(cmd, params)
			# renderModel[id] = result

		self.__profile.setWorkingPath(oldWorkingPath)


	def __createPage(self, slug, title, content):
		contentParser = konstrukteur.ContentParser.ContentParser(self.extensions, self.__fixJasyCommands, self.defaultLanguage)
		return contentParser.generateFields({
			"slug": slug,
			"title": title,
			"content": content
		}, self.__languages)


	def __generatePostIndex(self):
		indexPages = []
		itemsInIndex = self.config["blog"]["itemsInIndex"]

		if not type(self.config["blog"]["indexTitle"]) == dict:
			indexTitleLang = {}
			for language in self.__languages:
				indexTitleLang[language] = self.config["blog"]["indexTitle"]
			self.config["blog"]["indexTitle"] = indexTitleLang

		for language in self.__languages:

			indexTitle = self.config["blog"]["indexTitle"][language] if "indexTitle" in self.config["blog"] else "Index %d"
			sortedPosts = sorted([post for post in self.__posts if post["lang"] == language], key=self.__postSorter)

			pos = 0
			page = 1
			while pos < len(sortedPosts):
				self.__renderer.render(indexTitle, {
					"current" : {
						"pageno" : page,
						"lang" : language
					}
				})
				indexPage = self.__createPage("index-%d" % page, indexTitle, "")
				indexPages.append(indexPage)

				indexPage["post"] = sortedPosts[pos:itemsInIndex+pos]
				indexPage["pageno"] = page

				pos += itemsInIndex
				page += 1

		return indexPages



	def __outputContent(self):
		""" Output processed content to HTML """

		Console.info("Generating public files...")
		Console.indent()

		# Post process dates as iso string
		# TODO: Move to parser engine
		if self.__posts:
			for post in self.__posts:
				post["date"] = post["date"].isoformat()


		# Process all content types
		# Posts must be generated before archive
		for contentType in ["post", "archive", "page"]:
			if contentType == "post":
				urlGenerator = self.__postUrl
				items = self.__posts
			elif contentType == "archive":
				urlGenerator = self.config["blog"]["archiveUrl"]
				items = self.__generatePostIndex()
			elif contentType == "page":
				urlGenerator = self.__pageUrl
				items = self.__pages

			length = len(items)
			for position, currentItem in enumerate(items):
				Console.info("Generating %s %s/%s: %s...", contentType, position+1, length, currentItem["slug"])

				renderModel = self.__generateRenderModel(self.__pages, currentItem, contentType)

				if "url" in currentItem:
					processedFilename = currentItem["url"]
				else:
					processedFilename = self.__renderer.render(urlGenerator, renderModel)

				outputFilename = self.__profile.expandFileName(os.path.join(self.__profile.getDestinationPath(), processedFilename))

				# Use cache for speed-up re-runs
				# Using for pages and posts only as archive pages depend on changes in any of these
				if contentType == "archive":
					cacheId = None
					resultContent = None
				else:
					cacheId = "%s-%s-%s-%s" % (contentType, currentItem["slug"], currentItem["date"], self.__profile.getId())
					resultContent = self.__cache.read(cacheId, currentItem["mtime"])

				# Check cache validity
				if resultContent is None:
					self.__refreshUrls(items, currentItem, urlGenerator)
					if contentType == "archive":
						for cp in items:
							self.__refreshUrls(currentItem["post"], cp, self.__postUrl)

					self.__jasyCommandsHandling(renderModel, outputFilename)

					outputContent = self.__processOutputContent(renderModel, contentType)
					resultContent = konstrukteur.HtmlBeautifier.beautify(outputContent)

					# Store result into cache when caching is enabled (non archive pages only)
					if cacheId:
						self.__cache.store(cacheId, resultContent, currentItem["mtime"])

				# Write actual output file
				self.__fileManager.writeFile(outputFilename, resultContent)

		Console.outdent()

		if self.__posts:
			Console.info("Generating feed...")
			Console.indent()

			for language in self.__languages:
				sortedPosts = sorted([post for post in self.__posts if post["lang"] == language], key=self.__postSorter)

				renderModel = {
					'config' : self.config,
					'site' : {
						'name' : self.sitename,
						'url' : self.siteurl
					},
					"current" : {
						"lang" : language
					},
					"now" : datetime.datetime.now(tz=dateutil.tz.tzlocal()).replace(microsecond=0).isoformat(),
					"post" : sortedPosts[:self.config["blog"]["itemsInFeed"]]
				}


				feedUrl = self.__renderer.render(self.__feedUrl, renderModel)
				renderModel["feedurl"] = feedUrl

				outputContent = self.__safeRenderer.render(self.__templates["%s.Feed" % self.theme], renderModel)
				outputFilename = self.__profile.expandFileName(os.path.join(self.__profile.getDestinationPath(), feedUrl))
				self.__fileManager.writeFile(outputFilename, outputContent)

			Console.outdent()


	def __postSorter(self, item):
		return item["date"]


	def __generateRenderModel(self, pages, currentItem, pageType):
		res = {}

		res["type"] = pageType
		res["current"] = currentItem
		res["pages"] = self.__filterAndSortPages(pages, currentItem)
		res["config"] = dict(itertools.chain(self.config.items(), {
			"sitename" : self.sitename,
			"siteurl" : self.siteurl
		}.items()))
		res["languages"] = self.__mapLanguages(self.__languages, currentItem)

		return res



	def __processOutputContent(self, renderModel, type):
		pageName = "%(theme)s.%(type)s" % {
			"theme": self.theme,
			"type": type[0].upper() + type[1:]
		}

		if not pageName in self.__templates:
			raise RuntimeError("Template %s not found" % pageName)

		pageTemplate = self.__templates[pageName]

		#serialized = json.dumps(renderModel, sort_keys=True, indent=2, separators=(',', ': '))
		#print("MODEL")
		#print(serialized)

		return self.__renderer.render(pageTemplate, renderModel)
