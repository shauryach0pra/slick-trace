import { FAMILY_LABEL, FAMILY_SHORT } from './families';
import './familyChips.css';

/**
 * Filter by case family: "All" plus one chip per family present in the case
 * list, each with its count from that list. Filtering only changes what is
 * shown; the case list itself, and every case's data, are untouched.
 */
export default function FamilyChips({ incidents, value, onChange, className = '' }) {
  const order = [];
  const count = {};
  for (const c of incidents) {
    if (!(c.family in count)) { order.push(c.family); count[c.family] = 0; }
    count[c.family] += 1;
  }
  if (order.length < 2) return null;
  const chip = (key, label, n, title) => (
    <button type="button" key={key} className={`fchip${value === key ? ' is-on' : ''}`} aria-pressed={value === key}
            title={title} onClick={() => onChange(key)}>
      {label}<span className="fchip-n">{n}</span>
    </button>
  );
  return (
    <div className={`fchips ${className}`} role="group" aria-label="Filter cases by family">
      {chip('all', 'All', incidents.length, 'Every case')}
      {order.map((f) => chip(f, FAMILY_SHORT[f] ?? f, count[f], FAMILY_LABEL[f] ?? f))}
    </div>
  );
}
