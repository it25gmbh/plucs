#!/bin/bash

TMPF=/tmp/set_default_domain.tmp
trap "rm -f ${TMPF}" EXIT

eval "$(ucr shell)"

for type in domaincontroller_master domaincontroller_slave domaincontroller_backup memberserver; do
	udm computers/${type} list | grep -i 'xmppdomains:' | cut -f 2 -d ':'
done >${TMPF}

COUNT=`wc -l <${TMPF}`

if [ "${COUNT}" = '1' ] ; then
	DOM=`cat ${TMPF} | xargs`
	echo "Setting default XMPP domain for new users to '${DOM}'"
	udm settings/extended_attribute modify \
		--dn="cn=UniventionXMPP-User-Domain,cn=xmpp,cn=custom attributes,cn=univention,$ldap_base" \
		--set default=${DOM}
fi


