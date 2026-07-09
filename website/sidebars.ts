import type {SidebarsConfig} from '@docusaurus/plugin-content-docs';

const sidebars: SidebarsConfig = {
  docsSidebar: [
    'overview',
    'architecture',
    {
      type: 'category',
      label: 'Services',
      items: [
        'circuit-breaker',
        'chaos-toolkit',
        'slo-platform',
        'dashboard',
        'gateway',
      ],
    },
    {
      type: 'category',
      label: 'Advanced Features',
      items: [
        'dtmc-predictor',
        'graph-monitor',
        'scenario-proposer',
        'otel-genai',
        'trust-score',
      ],
    },
    {
      type: 'category',
      label: 'Operations',
      items: [
        'deployment',
        'rate-limiting',
        'ci-cd',
      ],
    },
    'api-reference',
  ],
};

export default sidebars;
