#!/bin/bash

cp rom/LostVikings.sfc rom/LostVikingsM.sfc
source="mod/${1:-bank_80.asm}"
asar "$source" rom/LostVikingsM.sfc
