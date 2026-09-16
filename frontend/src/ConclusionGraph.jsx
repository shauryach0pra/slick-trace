import { useMemo } from 'react';

export default function ConclusionGraph({ attribution, naive, historical, manifest, detection, fragility, forecast, coverage, nextObs }) {
  const nodes = useMemo(() => {
    const nodeList = [
      {
        id: 'scene',
        label: 'Scene Detection',
        status: detection ? 'detected' : 'no_data',
        value: detection ? `IoU: ${detection.iou?.toFixed(3) || 'N/A'}` : 'No detection data',
        position: { x: 20, y: 60 }
      },
      {
        id: 'proximity',
        label: 'Proximity Baseline',
        status: naive ? 'analyzed' : 'no_data',
        value: naive ? `Top: ${naive.top_candidate_id}` : 'No baseline data',
        position: { x: 240, y: 60 }
      },
      {
        id: 'attribution',
        label: 'Forward Attribution',
        status: attribution ? 'analyzed' : 'no_data',
        value: attribution ? `Top: ${attribution.top_candidate_id}` : 'No attribution data',
        position: { x: 460, y: 60 }
      },
      {
        id: 'historical',
        label: 'Historical Mapping',
        status: historical ? 'mapped' : 'no_data',
        value: historical ? `${historical.candidates?.length || 0} candidates` : 'No historical data',
        position: { x: 680, y: 60 }
      },
      {
        id: 'fragility',
        label: 'Fragility Analysis',
        status: fragility ? 'analyzed' : 'no_data',
        value: fragility ? `Flip: ${fragility.flip_delta || 'N/A'}` : 'No fragility data',
        position: { x: 900, y: 60 }
      },
      {
        id: 'conclusion',
        label: 'Final Conclusion',
        status: attribution ? 'concluded' : 'pending',
        value: attribution ?
          (attribution.top_candidate_id !== naive?.top_candidate_id ?
            `Source: ${attribution.top_candidate_id} (not nearest)` :
            `Source: ${attribution.top_candidate_id}`) :
          'Insufficient data',
        position: { x: 1120, y: 60 },
        isConclusion: true
      }
    ];

    return nodeList;
  }, [attribution, naive, historical, detection, fragility]);

  const edges = useMemo(() => {
    return [
      { from: 'scene', to: 'proximity' },
      { from: 'proximity', to: 'attribution' },
      { from: 'attribution', to: 'historical' },
      { from: 'historical', to: 'fragility' },
      { from: 'fragility', to: 'conclusion' }
    ];
  }, []);

  const getStatusColor = (status) => {
    switch (status) {
      case 'detected':
      case 'analyzed':
      case 'mapped':
      case 'concluded':
        return 'var(--green)';
      case 'no_data':
      case 'pending':
        return 'var(--line-subtle)';
      default:
        return 'var(--text-mid)';
    }
  };

  return (
    <div className="panel conclusion-graph">
      <div className="panel-head">
        <h2>Conclusion Graph</h2>
        <span className="tag tag-teal">Decision Flow</span>
      </div>
      <div className="graph-container">
        <svg className="graph-svg" width="1300" height="200" viewBox="0 0 1300 200">
          {/* Edges */}
          {edges.map((edge, i) => {
            const fromNode = nodes.find(n => n.id === edge.from);
            const toNode = nodes.find(n => n.id === edge.to);
            if (!fromNode || !toNode) return null;
            
            return (
              <line
                key={i}
                x1={fromNode.position.x + 160}
                y1={fromNode.position.y + 40}
                x2={toNode.position.x - 4}
                y2={toNode.position.y + 40}
                stroke="var(--line-subtle)"
                strokeWidth="1.5"
                markerEnd="url(#arrowhead)"
              />
            );
          })}
          
          {/* Arrow marker */}
          <defs>
            <marker
              id="arrowhead"
              markerWidth="10"
              markerHeight="7"
              refX="9"
              refY="3.5"
              orient="auto"
            >
              <polygon
                points="0 0, 10 3.5, 0 7"
                fill="var(--line-subtle)"
              />
            </marker>
          </defs>

          {/* Nodes */}
          {nodes.map((node) => (
            <g key={node.id} transform={`translate(${node.position.x}, ${node.position.y})`}>
              <rect
                x="0"
                y="0"
                width="160"
                height="80"
                rx="10"
                fill={node.isConclusion ? 'var(--teal)' : 'rgba(255, 255, 255, 0.9)'}
                stroke={getStatusColor(node.status)}
                strokeWidth="1.5"
              />
              <text
                x="80"
                y="25"
                textAnchor="middle"
                fill={node.isConclusion ? 'white' : 'var(--text-hi)'}
                fontSize="12"
                fontWeight="600"
                fontFamily="var(--font-display)"
              >
                {node.label}
              </text>
              <text
                x="80"
                y="50"
                textAnchor="middle"
                fill={node.isConclusion ? 'white' : 'var(--text-mid)'}
                fontSize="10"
                fontFamily="var(--font-body)"
              >
                {node.value}
              </text>
            </g>
          ))}
        </svg>
      </div>
    </div>
  );
}