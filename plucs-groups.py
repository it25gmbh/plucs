# -*- coding: utf-8 -*-
#
# PLUCS (XMPP integration for UCS)
"""PLUCS GROUPS listener module."""
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
import os
import io
import re
import marshal

name = 'plucs-groups'
description = 'Converts group lists into eJabberD ACLs'

filter = '(|(objectClass=univentionXMPPGroup)(objectClass=univentionXMPPAccount))'
attributes = ['cn','memberUid','uid','xmppEnabled']

# set to true when handler really got a change
changed = False

# track 'need-to-be-initialized'
initialized = False

# static storage of groups and users currently known
_dumpfile = os.path.join('/var','cache','plucs',name + '.cache')

_groups = {}
_gname = {}
_users = []

def initialize():
	"""Initialize the module once on first start or after clean."""
	
	ud.debug(ud.LISTENER, ud.INFO, 'plucs-groups: initialize() called')
	global initialized
	
	if _read_saved_data():
		_write_config()
	
	ud.debug(ud.LISTENER, ud.PROCESS, 'plucs-groups: initialized')
	
	initialized = True

def handler(dn, new, old):
	"""Handle changes to 'dn'."""
	global initialized
	global changed
	
	ud.debug(ud.LISTENER, ud.INFO, "plucs-groups: DN '%s' changed" % dn)

	if (not initialized):
		ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: initializing on first invocation.")
		initialize()
	
	
	# handle changes to users
	if (dn[0:4] == 'uid='):
		# user appeared or changed?
		if (new):
			enab = (new.get('xmppEnabled')[0] == 'TRUE')
			uid = new.get('uid')[0]

			if enab:
				_add_user(uid)
			else:
				_del_user(uid)

		# user removed?
		else:
			uid = old.get('uid')[0]
			_del_user(uid)
		
	# handle changes to groups
	elif (dn[0:3] == 'cn='):
		
		# modified groups are always removed and readded, this covers all kinds
		# of change (modrdn, xmppEnabled, members).
		if (old):		
			grpn = _sane_groupname(old.get('cn')[0])
			_del_group(grpn)
			
		if (new):
			gn = new.get('cn')[0]
			grpn = _sane_groupname(gn)
			enab = (new.get('xmppEnabled')[0] == 'TRUE')
			if enab:
				_add_group(grpn,gn,new.get('memberUid'))
	
	# should never happen
	else:
		ud.debug(ud.LISTENER, ud.WARN,"plucs-groups: don't know how to handle DN '%s'" % dn)

	changed = True
	_write_config()
	_save_data()
	
def clean():
	"""Handle request to clean-up the module."""
	global _groups
	global _gname
	global _users
	
	ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: cleanup requested.")
	
	try:
		_groups = {}
		_gname = {}
		_users = []
		os.unlink(_dumpfile)
	except:
		pass

def postrun():
	"""handle changes after at least 15s of no-changes"""
	ud.debug(ud.LISTENER, ud.INFO, "postrun: plucs-groups running")
	
	global changed
	
	if not changed:
		ud.debug(ud.LISTENER, ud.INFO, "plucs-groups: nothing changed, not restarting daemon.")
		return
		
	changed = False

	# set UID 0 and run the to-be-found-command to reload ACLs into an Erlang node
	ud.debug(ud.LISTENER, ud.PROCESS, "plucs-groups: reloading ACLs (%d users, %d groups)" % (len(_users),len(_groups.keys())))
	
	# Currently: reload eJabberd.
	try:
		listener.run('/usr/sbin/invoke-rc.d', ['invoke-rc.d', 'plucs', 'restart'], uid=0)
	except Exception, e:
		ud.debug(ud.ADMIN, ud.WARN, 'The restart of the PLUCS server failed: %s' % str(e))

# --------------- helper functions ------------------

def _write_config():
	"""write our static data into the config file"""
		
	listener.setuid(0)
	f = io.open('/etc/ejabberd/mod_filter_groups.cfg','w',encoding='utf-8')
	f.write(u"%% ---------------------------------------------------------\n")
	f.write(u"%% Group ACL file for eJabberD (PLUCS) XMPP service\n")
	f.write(u"%% Please don't edit this file by hand, it will be overwritten\n")
	f.write(u"%% by the next change to any XMPP-enabled group/user.\n")
	f.write(u"%% ---------------------------------------------------------\n\n")

	for g in _groups.keys():
		if _groups[g]:
			utemp = []
			for u in _groups[g]:
				if u in _users:
					utemp.append(u)
			if len(utemp):
				f.write(u"%% ------- %s ------\n" % _gname[g])
				for u in utemp:
					f.write(u"{acl, %s, {user, \"%s\"}}.\n" % (g,u))
		
	f.close()
	listener.unsetuid()

# ----------------- users -------------------

def _add_user(uid):
	"""add the given user to our internal list"""

	if not uid in _users:
		_users.append(uid)

def _del_user(uid):
	"""remove the given user from our internal list"""
	
	if uid in _users:
		_users.remove(uid)

# -------------- groups ----------------------

def _add_group(grp,name,users):
	"""add (or update / overwrite) a group"""

	_groups[grp] = users
	_gname[grp] = name

def _del_group(grp):
	"""remove a group"""
	
	if grp in _groups.keys():
		del _groups[grp]
		
	if grp in _gname.keys():
		del _gname[grp]

def _sane_groupname(grp):
	"""Sanitize a (possibly UTF-8) group name for use as an Erlang symbol"""
	#g = grp.casefold()		# Python >=3.3 only! 
	g = grp.lower()
	g = re.sub('[^a-z0-9]+','_',g)
	g = g.strip('_')
	return g

# --------------- files ----------------------
def _read_saved_data():
	"""Read saved arrays _users and _groups into memory"""
	global _groups
	global _gname
	global _users

	try:
		f = open(_dumpfile,'rb')
		t = marshal.load(f)
		f.close()
		if 'groups' in t.keys():
			_groups = t['groups']
		if 'gname' in t.keys():
			_gname = t['gname']
		if 'users' in t.keys():
			_users = t['users']
		ud.debug(ud.LISTENER,ud.PROCESS,"plucs-groups: read %d users, %d groups from cache" % (len(_users),len(_groups.keys())))
		return True
			
	except Exception,e:
		ud.debug(ud.LISTENER, ud.WARN,
		"%s: could not read dump file %s: %s" % (name, _dumpfile, str(e)))
		return False

def _save_data():
	"""Saves arrays _users and _groups across restarts"""
	
	try:
		t = {
			'groups':	_groups,
			'gname':	_gname,
			'users':	_users
			}
		f = open(_dumpfile,'wb')
		marshal.dump(t,f)
		f.close()
		ud.debug(ud.LISTENER,ud.INFO,"plucs-groups: cached %d users, %d groups" % (len(_users),len(_groups.keys())))

	except Exception,e:
		ud.debug(ud.LISTENER, ud.ERROR,
		"%s: could not write dump file %s: %s" % (name, _dumpfile, str(e)))
		                                                                
