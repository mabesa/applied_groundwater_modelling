#!/bin/sh
# Transport stale-number audit.  Run from repo root:  sh _SUPPORT/src/scripts/transport_stale_number_audit.sh
#
# TIER 1 (default, AC-grade): precise value-literal search over the three superseded eras
#   (1,080 m3/d, FR.1, FR.2).  Prose hyphenates, so day-41 and "day 41" are both matched.
#   AC: every remaining hit must classify as HISTORICAL ("was X at 1,080") or SYNTHETIC (_dummy).
#
# TIER 2 (sh ... --sweep): INDEPENDENT context sweep -- every line carrying a RESULT WORD and a
#   NUMBER (981 lines at 5afe4aa).  NOT a strict superset: it misses 26 Tier-1 lines, 21 stale.
#   A second, differently-shaped net.  Work it ONCE during P3, then rely on Tier 1.
#
# Excluded by design: _SUPPORT/src/golden/*.manifest.json (machine data; 0.684... matches 0.68)
#   and _SUPPORT/src/scripts/fr2_capture_transport_numbers.py (holds OLD values as its OLD->NEW table).
PATHS='PROJECT/transport PROJECT/workspace/template
  _SUPPORT/src/transport_prt_capture.py _SUPPORT/src/transport_srcpulse_demo.py
  _SUPPORT/src/transport_verify_2d.py _SUPPORT/src/transport_base_model.py
  _SUPPORT/src/scripts/scripts_exercises/tasks_data.py
  _SUPPORT/tests/test_transport_prt_capture.py _SUPPORT/tests/test_transport_srcpulse_demo.py
  _SUPPORT/tests/test_transport_verify_2d.py docs README.md'

V1='5\.1[0-9]? mg/L|day[ -]41|41\.25|38\.75|2\.95|4\.3 mg/L|day[ -]59|59\.1|3\.16'
V2='≈ ?76 m|~76 m|78\.9|108\.1|114 m|≈ ?112|~104-112|82\.9|90\.3|86\.9|0\.68|0\.71[0-9]|0\.72[0-9]?'
V3='3\.21|3\.24|24\.6|≈ ?25 d|22\.7|28\.6|83\.6|2\.745|32\.8|40\.7|48\.2|~18%|~33%|28\.0'
V4='~100\.2 m|≈ ?100 m|~100 m|~75\.9 m|~86\.7 m|~65\.2 m|5\.9-7\.2|5\.9–7\.2|95-117|95–117|~1%'
V5='04t §5|04t Section 5'

if [ "$1" = "--sweep" ]; then
  R='half-?width|capture fraction|asymptot|y_max|peak|arrival|travel time|breakthrough|centroid|arc length|path-averaged|m/d|mg/L|Pe_L|Pe_T|q ?\*? ?b|exceed|threshold|§[0-9]|Section [0-9]'
  N='[0-9]+\.[0-9]+|[0-9]{2,}|day[ -][0-9]+|~[0-9]+%|≈ ?[0-9]+'
  grep -rInE "($R)" $PATHS 2>/dev/null | grep -E "($N)"
else
  grep -rInE "($V1|$V2|$V3|$V4|$V5)" $PATHS 2>/dev/null
fi
