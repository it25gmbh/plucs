#!/bin/bash

# Fetch mod_filter.erl from current GIT. Without args, it fetches HEAD
# of the MASTER branch. If an arg is given it is to be interpreted as
# a commit id (full length!)

set -e

HERE=`dirname $0`
HERE=`cd ${HERE}; pwd`
BASE=`pwd`

if [ -n "$1" ] ; then
	COMMIT=$1
	echo "Choosing commit '${COMMIT}'" >&2
	URL="https://github.com/knobo/mod_filter/archive/${COMMIT}.zip"
else
	echo "Choosing HEAD revision of MASTER branch" >&2
	URL='https://github.com/knobo/mod_filter/archive/master.zip'
fi

cd ${BASE}
mkdir -p upstream
cd upstream

rm -f mod_filter.erl mod_filter.zip

echo "Getting current version of mod_filter" >&2
wget -O mod_filter.zip "${URL}" 2>/dev/null

echo "Unpacking mod_filter.erl..." >&2
unzip -j -o -x mod_filter.zip '**mod_filter.erl'
