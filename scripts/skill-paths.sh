#!/usr/bin/env bash
# Source this to get the newest Boomi skill script directories:
#   source scripts/skill-paths.sh && bash "$BI/boomi-env-check.sh"
# BI = boomi-integration scripts, DH = boomi-datahub scripts.
BI=$(ls -d ~/.claude/plugins/cache/boomi-companion/bc-integration/*/skills/boomi-integration/scripts | sort -V | tail -1)
DH=$(ls -d ~/.claude/plugins/cache/boomi-companion/bc-datahub/*/skills/boomi-datahub/scripts | sort -V | tail -1)
export BI DH
