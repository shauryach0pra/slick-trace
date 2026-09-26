// How each case family is described, shared by the sidebar and the overview.
// A family says what kind of test a case is, never which vessel did it.
export const FAMILY_LABEL = {
  decoy: 'nearest vessel is a decoy',
  moving_discharge: 'discharge while under way',
  absent_source: 'source not in the scene',
  crowded: 'crowded traffic',
  along_track_ribbon: 'ribbon laid along track',
};

// Short names for the filter chips, where the descriptions above are too long.
export const FAMILY_SHORT = {
  decoy: 'Decoy',
  moving_discharge: 'Under way',
  absent_source: 'Source absent',
  crowded: 'Crowded',
  along_track_ribbon: 'Ribbon',
};
