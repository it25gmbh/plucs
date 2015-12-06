#!/bin/bash

# The whole build process of eJabberD, just to get a compatible mod_filter.beam.

set -e

HERE=`dirname $0`
HERE=`cd ${HERE}; pwd`

cd ${HERE}/../..
mkdir -p mod_filter
cd mod_filter
export BASE=`pwd`

# file already there? no need to build it.
[ -s mod_filter.beam ] && exit 0

# Current use: we build for eJabberD 2.1.10 and use the last commit that
# is compatible with that version.

VERSION=${1:-2.1.10}
COMMIT=${2:-1ca3873780efaacf04c2f59e7bc96db798671c94}

${HERE}/get_upstream_source.sh ${VERSION}
${HERE}/get_module_source.sh ${COMMIT}
${HERE}/build_ejabberd.sh ${VERSION}
