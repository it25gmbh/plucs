#!/bin/bash

# Build eJabberD from source. We're currently using the same sources
# that were used by Debian when compiling a 2.x version.
#
# Whole purpose of this build is to get mod_filter.beam in a way
# compatible with the eJabberD version we're using.

set -e

HERE=`dirname $0`
HERE=`cd ${HERE}; pwd`
BASE=`pwd`

VERSION=$1

cd upstream
ORIG_ARCH=`ls *orig*gz | grep -F ${VERSION}`
if [ -z "${ORIG_ARCH}" ] ; then
	echo "No source archive for version '${VERSION}' found" >&2
	exit 1
fi

echo "Starting build for version '${VERSION}'" >&2

cd ${BASE}
if [ -d build ] ; then
	echo "  cleaning up previous build directory" >&2
	rm -rf build
fi

mkdir -p build
cd build

echo "  unpacking ${ORIG_ARCH}" >&2
tar -xzf ../upstream/${ORIG_ARCH}

BUILDDIR=ejabberd-${VERSION}
if [ ! -d ${BUILDDIR} ] ; then
	echo "Source archive possibly corrupt, could not find build" >&2
	echo "directory '${BUILDDIR}' inside." >&2
	exit 1
fi

cd ${BUILDDIR}
PATCHES=`ls ../../upstream/ejabberd_${VERSION}*diff* 2>/dev/null || true`
if [ -z "${PATCHES}" ] ; then
	echo "  No patches to apply" >&2
else
	echo "  patching source tree" >&2
	for p in ${PATCHES}; do
		echo "    ${p}"
		gunzip -f <${p} | patch -s -p0
	done
fi

cd src
echo "  including mod_filter source" >&2

# The version retrieved from GIT is not the right one, it is too new (ejabberd 13+)
# and does not even compile. We have downloaded an older version, also from GIT (the initial
# version as taken from the Bugzilla repo) and saved it manually into mod_filter.erl.
#
# We let the other code in place because upstream Debian has already switched to the
# new versioning scheme; only with Univention we're lagging a bit behind.
if false; then
	# we don't really know in which subdirectory the file resides, so let's
	# list the archive, retrieve the full name, and then extract the file
	# without path into the current directory.
	ARCHIVE=${BASE}/upstream/mod_filter.zip
	FNAME=`unzip -l ${ARCHIVE} | grep -F mod_filter.erl | awk '{print $NF;}'`
	unzip -j ${ARCHIVE} ${FNAME}
	sleep 5
else
	cp -v ${BASE}/upstream/mod_filter.erl .
fi

./configure
make

# If all went ok, we now have a mod_filter.beam in the current directory,
# let's copy that one level beyond the top of our build root.

cp -v mod_filter.beam ../../..
