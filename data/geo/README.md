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

**A reference overlay, not an input.** The forecast intersects the *synthetic*
coastline in each manifest. This one is drawn alongside it so the difference
between the model's geography and the real coast is visible; replacing the
synthetic coastline would silently change every forecast result.
