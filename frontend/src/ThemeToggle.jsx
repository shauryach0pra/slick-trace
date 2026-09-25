import { useEffect, useRef, useState } from 'react';

/**
 * Appearance control: System, Light or Dark, as a macOS segmented control.
 *
 * "System" removes the override so prefers-color-scheme decides, which is
 * what a native app does by default. The choice persists in localStorage;
 * index.html applies it before first paint so the page never flashes the
 * wrong theme. A radiogroup, so arrow keys move between the three options.
 */

const KEY = 'slicktrace-appearance';
const OPTIONS = [
  { value: 'system', label: 'Match system appearance' },
  { value: 'light', label: 'Light appearance' },
  { value: 'dark', label: 'Dark appearance' },
];

function readStored() {
  try {
    const v = localStorage.getItem(KEY);
    return OPTIONS.some((o) => o.value === v) ? v : 'system';
  } catch {
    return 'system';
  }
}

function apply(value) {
  const root = document.documentElement;
  if (value === 'system') delete root.dataset.theme;
  else root.dataset.theme = value;
}

function Icon({ name }) {
  if (name === 'light') {
    return (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"
           strokeLinecap="round" aria-hidden="true">
        <circle cx="8" cy="8" r="3" />
        <path d="M8 1.5v1.4M8 13.1v1.4M1.5 8h1.4M13.1 8h1.4M3.4 3.4l1 1M11.6 11.6l1 1M3.4 12.6l1-1M11.6 4.4l1-1" />
      </svg>
    );
  }
  if (name === 'dark') {
    return (
      <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"
           strokeLinejoin="round" aria-hidden="true">
        <path d="M13.2 10.1A5.6 5.6 0 0 1 5.9 2.8a5.6 5.6 0 1 0 7.3 7.3Z" />
      </svg>
    );
  }
  return (
    <svg viewBox="0 0 16 16" fill="none" stroke="currentColor" strokeWidth="1.4"
         strokeLinejoin="round" aria-hidden="true">
      <rect x="2" y="3" width="12" height="8.5" rx="1.6" />
      <path d="M6 14h4M8 11.5V14" strokeLinecap="round" />
    </svg>
  );
}

export default function ThemeToggle() {
  const [value, setValue] = useState(readStored);
  const refs = useRef([]);

  useEffect(() => {
    apply(value);
    try {
      if (value === 'system') localStorage.removeItem(KEY);
      else localStorage.setItem(KEY, value);
    } catch {
      /* storage unavailable: the choice lasts for this session only */
    }
  }, [value]);

  const index = OPTIONS.findIndex((o) => o.value === value);

  const onKeyDown = (e) => {
    const step = e.key === 'ArrowRight' || e.key === 'ArrowDown' ? 1
      : e.key === 'ArrowLeft' || e.key === 'ArrowUp' ? -1 : 0;
    if (!step) return;
    e.preventDefault();
    const next = (index + step + OPTIONS.length) % OPTIONS.length;
    setValue(OPTIONS[next].value);
    refs.current[next]?.focus();
  };

  return (
    <div className="theme-toggle" role="radiogroup" aria-label="Appearance"
         style={{ '--i': index }} onKeyDown={onKeyDown}>
      <span className="theme-toggle-thumb" aria-hidden="true" />
      {OPTIONS.map((o, i) => (
        <button
          key={o.value}
          ref={(el) => { refs.current[i] = el; }}
          type="button"
          role="radio"
          className="theme-seg"
          aria-checked={o.value === value}
          aria-label={o.label}
          title={o.label}
          tabIndex={o.value === value ? 0 : -1}
          onClick={() => setValue(o.value)}
        >
          <Icon name={o.value} />
        </button>
      ))}
    </div>
  );
}
