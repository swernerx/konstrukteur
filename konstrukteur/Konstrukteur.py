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
import jasy.core.Util as JasyUtil
import jasy.template.Parser as TemplateParser

from watchdog.observers import Observer
from watchdog.events import LoggingEventHandler

import konstrukteur.HtmlParser
import konstrukteur.HtmlBeautifier
import konstrukteur.Language
import konstrukteur.FileWatcher
import konstrukteur.ContentParser as ContentParser
import konstrukteur.Util as Util
import konstrukteur.TemplateCompiler as TemplateCompiler
import konstrukteur.Template as Template


class Konstrukteur:
	""" Core application class for Konstrukteur """

	config = None # Dict

	__siteName = None
	__siteUrl = None

	__theme = None

	__defaultLanguage = None # String
	__extensions = None # List

	__regenerate = False # Boolean
	__templates = None # List
	__pages = None # List
	__languages = None # Set
	__locales = None # Dict

	__postUrl = None # Template String
	__pageUrl = None # Template String
	__feedUrl = None # Template String
	__archiveUrl = None # Template String

	__renderer = None
	__fileManager = None


	def __init__(self, profile, regenerate=False, project=None):
		# Figuring out main project
		session = profile.getSession()
		main = project or session.getMain()

		self.__profile = profile
		self.__session = session
		self.__locales = {}
		self.__commandReplacer = []
		self.__id = 0
		self.__regenerate = not regenerate == False
		self.__cache = main.getCache()

		# Importing configuration from project
		self.config = main.getConfigValue("konstrukteur")

		self.__siteName = main.getConfigValue("konstrukteur.site.name", "Test website")
		self.__siteUrl = main.getConfigValue("konstrukteur.site.url", "//localhost")

		self.__pageUrl = main.getConfigValue("konstrukteur.pageUrl", "{{language}}/{{slug}}.html")

		self.__postUrl = main.getConfigValue("konstrukteur.blog.postUrl", "{{language}}/blog/{{slug}}.html")
		self.__archiveUrl = main.getConfigValue("konstrukteur.blog.archiveUrl", "archive.{{language}}-{{page}}.html")
		self.__feedUrl = main.getConfigValue("konstrukteur.blog.feedUrl", "feed.{{language}}.xml")

		self.__extensions = main.getConfigValue("konstrukteur.extensions", ["markdown", "html"])
		self.__theme = main.getConfigValue("konstrukteur.theme", main.getName())
		self.__defaultLanguage = main.getConfigValue("konstrukteur.defaultLanguage", "en")
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

		self.__pagePath = os.path.join(self.__contentPath, "page")
		self.__postPath = os.path.join(self.__contentPath, "post")

		if not os.path.exists(self.__templatePath):
			raise RuntimeError("Path to templates not found : %s" % self.__templatePath)
		if not os.path.exists(self.__contentPath):
			raise RuntimeError("Path to content not found : %s" % self.__contentPath)

		# A theme could be any project registered in the current session
		if self.__theme:
			themeProject = session.getProjectByName(self.__theme)
			if not themeProject:
				raise RuntimeError("Theme '%s' not found" % self.__theme)

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

			print("Compiled Template: ", name, "=>", compiled)


	def __parseContent(self):
		""" Parse all content items in users content directory """

		contentParser = ContentParser.ContentParser(self.__extensions, self.__defaultLanguage)

		Console.info("Parsing content...")
		Console.indent()

		self.__pages = contentParser.parse(self.__pagePath)
		self.__posts = contentParser.parse(self.__postPath)
		self.__languages = contentParser.getLanguages()

		Console.outdent()
		Console.info("Processing locales...")
		Console.indent()

		for language in self.__languages:
			self.__locales[language] = konstrukteur.Language.LocaleParser(language)

		Console.outdent()









	def __createPage(self, slug, title, content):
		contentParser = ContentParser.ContentParser(self.__extensions, self.__defaultLanguage)
		return contentParser.generateFields({
			"slug": slug,
			"title": title,
			"content": content
		}, self.__languages)


	def __generatePostIndex(self):
		indexPages = []
		archiveItemsPerPage = self.config["blog"]["archiveItemsPerPage"]

		if not type(self.config["blog"]["archiveTitle"]) == dict:
			indexTitleLang = {}
			for language in self.__languages:
				indexTitleLang[language] = self.config["blog"]["archiveTitle"]
			self.config["blog"]["archiveTitle"] = indexTitleLang

		for language in self.__languages:

			archiveTitle = self.config["blog"]["archiveTitle"][language] if "archiveTitle" in self.config["blog"] else "Index %d"
			sortedPosts = sorted([post for post in self.__posts if post["lang"] == language], key=self.__postSorter)

			pos = 0
			page = 1
			while pos < len(sortedPosts):
				self.__renderer.render(archiveTitle, {
					"current" : {
						"pageno" : page,
						"lang" : language
					}
				})
				indexPage = self.__createPage("index-%d" % page, archiveTitle, "")
				indexPages.append(indexPage)

				indexPage["post"] = sortedPosts[pos:archiveItemsPerPage+pos]
				indexPage["pageno"] = page

				pos += archiveItemsPerPage
				page += 1

		return indexPages



	def __outputContent(self):
		""" Output processed content to HTML """

		Console.info("Generating public files...")
		Console.indent()

		# Process all content types
		# Posts must be generated before archive
		for contentType in ["post", "archive", "page"]:
			if contentType == "post":
				urlTemplate = self.__postUrl
				items = self.__posts
			elif contentType == "archive":
				urlTemplate = self.__archiveUrl
				items = self.__generatePostIndex()
			elif contentType == "page":
				urlTemplate = self.__pageUrl
				items = self.__pages

			# Preparing template
			templateName = "%(theme)s.%(type)s" % {
				"theme": self.__theme,
				"type": contentType[0].upper() + contentType[1:]
			}

			if not templateName in self.__templates:
				raise RuntimeError("Template %s not found" % templateName)

			template = self.__templates[templateName]

			# Profile shorthands
			profileId = self.__profile.getId()
			destinationPath = self.__profile.getDestinationPath()

			# Create individual output files
			length = str(len(items))
			padding = len(length)

			for pos, currentItem in enumerate(items):
				itemSlug = currentItem["slug"]
				itemMtime = currentItem["mtime"]

				filePath = Util.replaceFields(urlTemplate, currentItem)
				outputFilename = os.path.join(destinationPath, filePath)

				Console.info("Generating %s %s/%s: %s...", contentType, str(pos+1).zfill(padding), length, outputFilename)

				renderModel = self.__generateRenderModel(currentItem, contentType)

				# Use cache for speed-up re-runs
				# Using for pages and posts only as archive pages depend on changes in any of these
				if contentType == "archive":
					cacheId = None
					resultContent = None
				else:
					cacheId = "%s-%s-%s" % (contentType, itemSlug, profileId)
					resultContent = self.__cache.read(cacheId, itemMtime)
					resultContent = None

				# Check cache validity
				if resultContent is None:
					resultContent = template.render(renderModel)

					# Store result into cache when caching is enabled (non archive pages only)
					if cacheId:
						self.__cache.store(cacheId, resultContent, itemMtime)

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
						'name' : self.__siteName,
						'url' : self.__siteUrl
					},
					"current" : {
						"lang" : language
					},
					"feedUrl" : feedUrl,
					"now" : datetime.datetime.now(tz=dateutil.tz.tzlocal()).replace(microsecond=0).isoformat(),
					"post" : sortedPosts[:self.config["blog"]["itemsInFeed"]]
				}

				outputContent = self.__safeRenderer.render(self.__templates["%s.Feed" % self.__theme], renderModel)
				outputFilename = self.__profile.expandFileName(os.path.join(self.__profile.getDestinationPath(), feedUrl))
				self.__fileManager.writeFile(outputFilename, outputContent)

			Console.outdent()




	def __postSorter(self, item):
		return item["date"]








	def __getItemLanguages(self, item):
		""" Annotate languges list with information about current language """

		if "translations" not in item:
			return None

		languages = self.__languages

		def languageMap(value):
			isCurrent = value == item["lang"]
			localizedName = self.__locales[value].getName(value)
			relativeUrl = "." if isCurrent else item["translations"][value]

			return {
				"code" : value,
				"name" : localizedName,
				"isCurrent" : isCurrent,
				"relativeUrl" : relativeUrl
			}

		return list(map(languageMap, languages))


	def __getFilteredPages(self, currentItem):
		""" Return sorted list of only pages of same language and not hidden """

		pages = self.__pages
		currentLang = currentItem["lang"]
		pageList = [ pageItem for pageItem in pages if pageItem["lang"] == currentLang and not pageItem["status"] == "hidden" ]

		return sorted(pageList, key=lambda pageItem: JasyUtil.getKey(pageItem, "pos", 1000000))


	def __generateRenderModel(self, currentItem, contentType):
		renderModel = {}

		renderModel["type"] = contentType
		renderModel["current"] = currentItem
		renderModel["pages"] = self.__getFilteredPages(currentItem)
		renderModel["config"] = self.config
		renderModel["languages"] = self.__getItemLanguages(currentItem)

		return renderModel
