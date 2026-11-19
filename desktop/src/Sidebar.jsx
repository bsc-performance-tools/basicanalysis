import React from 'react';

const ICONS = {
  overview: '◉', runtime: '▤', heterogeneous: '⇅', io: '⛁', 'gpu-hwc': '▦',
  scaling: '↗', 'openmp-runtime': '⋮', outer: '◫', inner: '◨',
};

/** Left menu with the views of the report, grouped as in the report. */
export default function Sidebar({ views, active, onOpen, onOpenBeside }) {
  const groups = [];
  for (const view of views) {
    let group = groups.find((g) => g.name === view.group);
    if (!group) { group = { name: view.group, views: [] }; groups.push(group); }
    group.views.push(view);
  }
  return (
    <nav className="sidebar">
      {groups.map((group) => (
        <div key={group.name} className="sidebar-group">
          <div className="sidebar-group-name">{group.name}</div>
          {group.views.map((view) => (
            <div key={view.id} className={`sidebar-item${active === view.id ? ' active' : ''}`}>
              <button type="button" className="sidebar-open" onClick={() => onOpen(view)}>
                <span className="sidebar-icon">{ICONS[view.id] || '•'}</span>{view.label}
              </button>
              <button type="button" className="sidebar-beside" title="Open beside (new panel)"
                      onClick={() => onOpenBeside(view)}>⧉</button>
            </div>
          ))}
        </div>
      ))}
    </nav>
  );
}
