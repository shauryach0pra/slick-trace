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

// What each kind of case tests, fully explained: the design of the case, never which vessel did it.
export const FAMILY_STORY = {
  decoy: 'The vessel nearest the slick when the image is taken is a decoy: it passed close by, but the oil came '
    + 'from a vessel whose track crossed the slick’s origin earlier.',
  moving_discharge: 'The oil was discharged while a vessel was under way, so the slick is stretched along its course '
    + 'rather than pooled around a stopped ship.',
  absent_source: 'The vessel that released the oil is not among the vessels in the data — as if it had left the scene '
    + 'or was never tracked — so the right answer is to name no one.',
  crowded: 'Many vessels crossed the area the oil could have come from, so being nearby, or crossing the area, cannot '
    + 'single out the source on its own.',
  along_track_ribbon: 'A long release was laid out along a vessel’s route, leaving a narrow ribbon of oil along its '
    + 'track rather than a compact patch.',
};
