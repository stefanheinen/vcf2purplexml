#!/bin/bash
sed '/PHOTO[.]*/,/^[^ ]/ s/^[ ].*$//g' $1 | sed '/^PHOTO.*/d' | sed '/^\s*$/d'
