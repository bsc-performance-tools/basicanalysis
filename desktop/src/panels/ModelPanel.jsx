import React from 'react';
import { useAnalysis } from '../App.jsx';
import ModelTable from './ModelTable.jsx';

export default function ModelPanel({ params }) {
  const { results } = useAnalysis();
  if (!results) return null;
  return (
    <div className="panel">
      <ModelTable modelId={params.modelId} />
    </div>
  );
}
