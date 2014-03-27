# Little helper to allow python modules in current jasylibrarys path
import sys, os.path, inspect
filename = inspect.getframeinfo(inspect.currentframe()).filename
path = os.path.dirname(os.path.abspath(filename))
sys.path.append(path)

import konstrukteur.Konstrukteur as Konstrukteur
import jasy.asset.Manager


@share
def build(profile, regenerate = False):
	""" Build static website """

	def getPartUrl(part, type):
		folder = ""
		if type == "css":
			folder = profile.getCssOutputFolder()
		elif type == "css":
			folder = profile.getJsOutputFolder()
		elif type == "template":
			folder = profile.getTemplateOutputFolder()
		else:
			raise Exception("Unsupported part type: %s" % type)

		outputPath = os.path.relpath(os.path.join(profile.getDestinationPath(), folder), profile.getWorkingPath())
		fileName = profile.expandFileName("%s/%s-{{id}}.%s" % (outputPath, part, type))

		return fileName

	profile.addCommand("part.url", getPartUrl, "url")

	site = Konstrukteur.Konstrukteur(profile, regenerate=regenerate)
	site.build()
