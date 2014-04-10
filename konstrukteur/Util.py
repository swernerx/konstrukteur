#
# Konstrukteur - Static Site Generator
# Copyright 2013-2014 Sebastian Fastner
# Copyright 2014 Sebastian Werner
#

import re
import unidecode
import json
import datetime


import jasy.core.Console as Console


def fixSlug(slug):
	""" Replaces unicode character with something equal from ascii ( e.g. ü -> u ) """

	pattern = r'[.\s]+'
	return re.sub(pattern, "-", unidecode.unidecode(slug).lower())


FIELDS_REGEX = re.compile(r"{{([a-zA-Z][a-zA-Z0-9\-\.]+)}}")

def replaceFields(input, data):
	def replacer(match):
		key = match.group(1)
		if key in data:
			return str(data[key])
		elif "." in key:
			current = data
			splits = key.split(".")
			for split in splits:
				if split in current:
					current = current[split]
				else:
					current = None
					break

			if current is not None:
				return str(current)

		Console.warn("No value for key: %s" % key)
		return match.group(0)

	return FIELDS_REGEX.sub(replacer, input)


class CustomJsonEncoder(json.JSONEncoder):
	def default(self, obj):
		if callable(obj):
			return "<callable>"

		elif isinstance(obj, datetime.date):
			return obj.isoformat()

		return json.JSONEncoder.default(self, obj)

def stringifyData(data):
	return json.dumps(data, sort_keys=True, indent=2, separators=(',', ': '), cls=CustomJsonEncoder)
