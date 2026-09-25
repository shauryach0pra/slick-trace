# Geographic reference data

## `coastline_mumbai.json`

Natural Earth 10m coastline, clipped to 71.6–73.6 E, 17.9–19.9 N — a margin
around every case bounding box. **Public domain**: Natural Earth places no
restrictions on use.

**Committed rather than fetched.** A basemap served from a tile provider would
end the offline operation this project verified in
`docs/evidence/smoke_offline.txt`, and self-hosted fonts were chosen for the
same reason. Seven kilobytes in the repository costs less than a network
dependency.

**The coastline every case uses.** Each manifest carries this coastline clipped
to its scene; the generator keeps vessels, slicks and fishing grounds off the
land east of it; the detector rejects land against it; and the forecast strands
oil that reaches it. One land test does all of it: `slicktrace_core/geography.py`,
point-in-polygon against the coastline closed around the land to its east.

An invented coastline about 19 km east of this one stood in for it until the
benchmark fix recorded in the CHANGELOG. On real imagery that put a synthetic
mangrove reserve over the city and part of a slick on land. Natural Earth 10 m is
scene-scale: narrow creeks and harbour detail are resolved only coarsely.
