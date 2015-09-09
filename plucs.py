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

name = 'plucs'
description = 'Reconfigures eJabberd service'

hostname = listener.baseConfig['hostname']
filter = '(&' + \
		'(objectClass=univentionXMPPHost)' + \
		'(cn=%s))' % hostname
attributes = ['xmppDomains','univentionService']

# set to true when handler really got a change
changed = False

def initialize():
	"""Initialize the module once on first start or after clean."""
	ud.debug(ud.LISTENER, ud.INFO, 'plucs: initialized')

def handler(dn, new, old):
	"""Handle changes to 'dn'."""
	global changed
	
	ucr = univention.config_registry.ConfigRegistry()
	ud.debug(ud.LISTENER, ud.INFO, "plucs: DN '%s' changed" % dn)
	ud.debug(ud.LISTENER, ud.INFO, "plucs:   old = '%s'" % old.get('xmppDomains'))
	ud.debug(ud.LISTENER, ud.INFO, "plucs:   new = '%s'" % new.get('xmppDomains'))

	# It should be possible to switch off an XMPP host by removing the
	# XMPP service entry, without losing its xmppDomains.
	hasService = 'XMPP' in new.get('univentionService')
	ud.debug(ud.LISTENER, ud.INFO, "plucs:   service XMPP = %s" % hasService)

	# Old LDAP value doesn't matter.
	# We have to compare with the old value currently stored in UCR.
	oldval = ucr.get('xmpp/domains')
	msg = ''
	if not hasService:
		msg = 'service XMPP not assigned'
		newval = ''
	elif new.get('xmppDomains') is None:
		msg = 'no XMPP domains set'
		newval = ''
	else:
		newval = ' '.join(new.get('xmppDomains'))
		if newval == '':
			msg = 'list of XMPP domains is empty'
			
	if msg != '':
		ud.debug(ud.LISTENER, ud.INFO, "plucs: %s" % msg)

	if oldval != newval:
		changed = True
		listener.setuid(0)
		ud.debug(ud.LISTENER, ud.INFO, "plucs: setting xmpp domains to '%s'" % newval)
		try:
			univention.config_registry.handler_set(['xmpp/domains=%s' % newval])
		finally:
			listener.unsetuid()

def clean():
	"""Handle request to clean-up the module."""
	return

def postrun():
	ud.debug(ud.LISTENER, ud.INFO, "postrun: plucs running")
	
	global changed
	if not changed:
		ud.debug(ud.LISTENER, ud.INFO, "plucs: nothing changed, not restarting daemon.")
		return
		
	changed = False

	ucr = univention.config_registry.ConfigRegistry()
	ucr.load()
	
	if ucr.is_true("plucs/autostart", False):
		if ucr.is_true('plucs/restart/listener', False):
			ud.debug(ud.LISTENER, ud.INFO, 'PLUCS: Restarting server')
			try:
				listener.run('/usr/sbin/invoke-rc.d', ['invoke-rc.d', 'plucs', 'restart'], uid=0)
			except Exception, e:
				ud.debug(ud.ADMIN, ud.WARN, 'The restart of the PLUCS server failed: %s' % str(e))
		else:
			ud.debug(ud.ADMIN, ud.INFO, 'PLUCS: the automatic restart of the PLUCS server by the listener is disabled. Set plucs/restart/listener to true to enable this option.')
	else:
		ud.debug(ud.LISTENER, ud.INFO, 'plucs: autostart disabled in config_registry - not started.')
