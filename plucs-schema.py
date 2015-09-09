# -*- coding: utf-8 -*-
#
# PLUCS (XMPP integration for UCS)
"""PLUCS listener module."""
#
# Copyright 2013-2014 it25 GmbH
#
# http://www.it25.de/
#
# All rights reserved.
#
# The source code of this program is made available
# under the terms of the GNU Affero General Public License version 3
# (GNU AGPL V3) as published by the Free Software Foundation.
#
# In the case you use this program under the terms of the GNU AGPL V3,
# the program is provided in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU Affero General Public License for more details.
#
# You should have received a copy of the GNU Affero General Public
# License with the Debian GNU/Linux or Univention distribution in file
# /usr/share/common-licenses/AGPL-3; if not, see
# <http://www.gnu.org/licenses/>.

# pylint: disable-msg=C0103,W0704

__package__ = ''	# workaround for PEP 366
import listener
import univention.debug as ud
import univention.config_registry
# import subprocess
import os

name = 'plucs-schema'
description = 'Sets XMPP default domain for new users'

filter = '(objectClass=univentionXMPPHost)'
attributes = ['xmppDomains']

def initialize():
	"""Initialize the module once on first start or after clean."""
	ud.debug(ud.LISTENER, ud.INFO, 'plucs: initialized')

def handler(dn, new, old):
	"""Handle changes to 'dn'."""
	
	ud.debug(ud.LISTENER, ud.INFO, "plucs: DN '%s' changed" % dn)
	ud.debug(ud.LISTENER, ud.INFO, "plucs:   old = '%s'" % old.get('xmppDomains'))
	ud.debug(ud.LISTENER, ud.INFO, "plucs:   new = '%s'" % new.get('xmppDomains'))

	listener.setuid(0)
	try:
		os.system('/usr/share/plucs-schema/set_default_domain.sh')
	finally:
		listener.unsetuid()

def clean():
	"""Handle request to clean-up the module."""
	return

def postrun():
	return
