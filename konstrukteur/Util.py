#
# Konstrukteur - Static Site Generator
# Copyright 2013-2014 Sebastian Fastner
# Copyright 2014 Sebastian Werner
#

import re
import unidecode


def fixSlug(slug):
	""" Replaces unicode character with something equal from ascii ( e.g. ü -> u ) """

	pattern = r'[.\s]+'
	return re.sub(pattern, "-", unidecode.unidecode(slug).lower())
