import React, { useEffect, useRef } from 'react';
import Plotly from 'plotly.js-basic-dist-min';

// Interactive plot (zoom, pan, hover, PNG export) that follows the size of
// its panel.
export default function Plot({ data, layout }) {
  const ref = useRef(null);
  useEffect(() => {
    const node = ref.current;
    if (!node) return undefined;
    Plotly.react(node, data, { autosize: true, margin: { l: 55, r: 60, t: 30, b: 70 }, ...layout },
                 { responsive: true, displaylogo: false });
    const resize = () => { if (node.offsetWidth > 0) Plotly.Plots.resize(node); };
    const observer = new ResizeObserver(resize);
    observer.observe(node);
    requestAnimationFrame(resize);
    return () => observer.disconnect();
  }, [data, layout]);
  // Free the plot when it is removed. The node is kept here: React clears
  // ref.current before this cleanup runs.
  useEffect(() => {
    const node = ref.current;
    return () => { if (node) Plotly.purge(node); };
  }, []);
  return <div ref={ref} className="plot" />;
}
