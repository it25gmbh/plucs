#!/bin/bash

# Get source of eJabberD from Debian's repository. Current desired version
# is 2.1.10 unless the script is called with a version number argument.

set -e

HERE=`dirname $0`
HERE=`cd ${HERE}; pwd`
BASE=`pwd`

VERSION=$1

FTPHOST=ftp.de.debian.org

TMPF=/tmp/get_upstream_source_$$.tmp
trap "rm -f ${TMPF}" EXIT

echo "Getting upstream source for version '${VERSION}' ..." >&2
echo "  retrieving file listing" >&2
wget -O - "ftp://anonymous@${FTPHOST}/debian/ls-lR.gz" 2>/dev/null | gunzip >${TMPF}

FILES=`grep -F ejabberd "${TMPF}" | grep -F "${VERSION}" | grep -Ei '\.gz$' | awk '{print $NF;}'`

# real files are in debian/pool/main/e/ejabberd/
# saved in './upstream'
cd ${BASE}
mkdir -p upstream
cd upstream
for f in ${FILES}; do
	if [ -e ${f} ] ; then
		echo "  ${f} already there" >&2
	else
		echo "  retrieving ${f}" >&2
		wget -O ${f} "ftp://anonymous@${FTPHOST}/debian/pool/main/e/ejabberd/${f}" 2>/dev/null
	fi
done

