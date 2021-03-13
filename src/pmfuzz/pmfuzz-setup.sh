#! /usr/bin/env sh
# Brief:
#   Sets up python environment for pmfuzz
# Usage:
#   ./pmfuzz-setup.sh

BASEDIR=$(dirname "$0")
LOG_F="$(mktemp /tmp/pmfuzz-setup.XXXXXX.log)"

LOG_TEXT=", check README. Log file at: ${LOG_F}"

echo "Log file: ${LOG_F}"
echo ''

# Check for virtual env
echo 'Finding virtualenv...'
command -v virtualenv >${LOG_F} 2>&1 \
    || { echo >&2 "ERROR: PMFuzz requires virtualenv." $LOG_TEXT ; 
         exit 1; }

# Create new virtual env
echo 'Setting up environment...'
virtualenv -q --python=python3 "${BASEDIR}/venv" >${LOG_F} 2>&1 \
    || { echo >&2 "ERROR: Unable to create virtual env" $LOG_TEXT; 
         exit 1; }

# Activate environment
echo 'Activating environment...'
source "${BASEDIR}/venv/bin/activate"  >${LOG_F} 2>&1 \
    || . "${BASEDIR}/venv/bin/activate"  >${LOG_F} 2>&1 \
    || { echo >&2 "ERROR: Unable to activate virtual env" $LOG_TEXT; 
         exit 1; }


# Install requirements
echo 'Installing dependencies...'
pip install -r requirements.txt  >${LOG_F} 2>&1 \
    || { echo >&2 "ERROR: Unable to install dependencies" $LOG_TEXT; 
         exit 1; }

echo ''
echo 'Done, run source venv/bin/activate before running pmfuzz'