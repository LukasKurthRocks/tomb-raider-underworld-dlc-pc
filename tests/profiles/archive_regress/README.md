# Archived regression profiles

Intermediate test profiles of 2026-11-01 .. 2026-11-03 (tests 48i-50k and their variants, the first TruGuard run,
`regress_dlc1`, `regress_shadowlara_50l_radial`, which TruMenu 0.10 could not hold). No current test package uses
them; the active packages build on `regress_shadowlara_50l_radial2`, `_50l_hud_radial2`, `_50l_pause_radial2`,
`_50o_radial2` and `regress_costumes_0311` in the folder above.

Kept so that old runs (`runs\<time>_<profile>`) stay reproducible. The test runner looks only in `tests\profiles`;
to run one of these again, copy it back there. Their plugin pins are as of the day they were archived and may point
to builds that no longer exist. Profiles that turn out to be really obsolete are deleted later.
