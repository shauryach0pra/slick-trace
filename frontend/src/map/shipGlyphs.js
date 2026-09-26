/**
 * Top-down vessel silhouettes, one per AIS ship type. Original drawings made
 * for this project (no third-party icon set), so they carry the repository's
 * own licence. Bow at the top; the map rotates each to its heading. Symbols,
 * not to scale: no vessel's dimensions are known.
 *
 * Every glyph uses the same classes - ship-body, ship-deck, ship-bridge - so
 * observed, projected and leading-candidate styling apply to all of them.
 */
const G = {
  // long hull, rounded bow; a pipe manifold across the deck; bridge aft
  tanker: '<path class="ship-body" d="M6 0.8C9.2 3.6 10.6 7.2 10.6 12.2V30.6Q10.6 33.4 6 33.4Q1.4 33.4 1.4 30.6V12.2C1.4 7.2 2.8 3.6 6 0.8Z"/>'
    + '<path class="ship-deck" d="M6 5V24.5M3 14.6H9"/><rect class="ship-bridge" x="2.8" y="25.2" width="6.4" height="4.6" rx="0.9"/>',
  // squarer hull; rows of container stacks; bridge aft
  cargo: '<path class="ship-body" d="M6 0.8C8.8 3 10.4 6 10.4 10V31.3Q10.4 33.4 8.6 33.4H3.4Q1.6 33.4 1.6 31.3V10C1.6 6 3.2 3 6 0.8Z"/>'
    + '<rect class="ship-bridge" x="3" y="8.6" width="6" height="3.4" rx="0.5"/><rect class="ship-bridge" x="3" y="13" width="6" height="3.4" rx="0.5"/>'
    + '<rect class="ship-bridge" x="3" y="17.4" width="6" height="3.4" rx="0.5"/><rect class="ship-bridge" x="3" y="21.8" width="6" height="3" rx="0.5"/>'
    + '<rect class="ship-bridge" x="2.6" y="26.4" width="6.8" height="3.6" rx="0.8"/>',
  // rounded hull under one long superstructure
  passenger: '<path class="ship-body" d="M6 1C9 4 10.4 8 10.4 13V29Q10.4 33.4 6 33.4Q1.6 33.4 1.6 29V13C1.6 8 3 4 6 1Z"/>'
    + '<rect class="ship-bridge" x="3" y="8.5" width="6" height="20" rx="2.4"/>',
  // short and beamy; wheelhouse forward, gantry aft
  fishing: '<path class="ship-body" d="M6 6C9.6 9 11 13 11 18V30Q11 33.4 6 33.4Q1 33.4 1 30V18C1 13 2.4 9 6 6Z"/>'
    + '<rect class="ship-bridge" x="3.5" y="12" width="5" height="5.2" rx="0.9"/><path class="ship-deck" d="M2.2 29.2H9.8M6 17.2V29.2"/>',
  // short, wide; bridge central; towing hook aft
  tug: '<path class="ship-body" d="M6 9C10 11 11.4 14.6 11.4 19V29.5Q11.4 33.4 6 33.4Q0.6 33.4 0.6 29.5V19C0.6 14.6 2 11 6 9Z"/>'
    + '<rect class="ship-bridge" x="3.4" y="16.6" width="5.2" height="5.4" rx="1"/><path class="ship-deck" d="M6 24.5V32.4M4 30.4H8"/>',
  // not reported: the generic hull
  other: '<path class="ship-body" d="M6 0.6C8.7 5.8 10.4 11.5 10.4 19.5V30.4Q10.4 33.4 6 33.4Q1.6 33.4 1.6 30.4V19.5C1.6 11.5 3.3 5.8 6 0.6Z"/>'
    + '<path class="ship-deck" d="M6 5.5V19"/><rect class="ship-bridge" x="3.1" y="21.5" width="5.8" height="5.4" rx="1.1"/>',
};
export const SHIP_TYPES = ['tanker', 'cargo', 'passenger', 'fishing', 'tug'];
export const TYPE_LABEL = { tanker: 'tanker', cargo: 'cargo', passenger: 'passenger', fishing: 'fishing', tug: 'tug',
                            other: 'type not reported' };
export function glyph(type) {
  return `<svg class="ship-hull" viewBox="0 0 12 34" aria-hidden="true">${G[type] ?? G.other}</svg>`;
}
