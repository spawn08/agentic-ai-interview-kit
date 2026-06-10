import type {ReactNode} from 'react';
import clsx from 'clsx';
import Heading from '@theme/Heading';
import styles from './styles.module.css';

type FeatureItem = {
  title: string;
  icon: string;
  description: ReactNode;
};

const FeatureList: FeatureItem[] = [
  {
    title: 'Learn the Foundations',
    icon: '\u{1F9E0}',
    description: (
      <>
        Start from LLM fundamentals, prompting, and RAG — then build up to
        agent architectures, memory systems, and tool use.
      </>
    ),
  },
  {
    title: 'Master Design Patterns',
    icon: '\u{1F3D7}\u{FE0F}',
    description: (
      <>
        Explore proven patterns like ReAct, multi-agent collaboration,
        plan-and-execute, and human-in-the-loop with real code examples.
      </>
    ),
  },
  {
    title: 'Ace the Interview',
    icon: '\u{1F3AF}',
    description: (
      <>
        Practice with system design case studies, coding challenges, and
        curated Q&A covering every major agentic AI topic.
      </>
    ),
  },
];

function Feature({title, icon, description}: FeatureItem) {
  return (
    <div className={clsx('col col--4')}>
      <div className="text--center">
        <span className={styles.featureIcon}>{icon}</span>
      </div>
      <div className="text--center padding-horiz--md">
        <Heading as="h3">{title}</Heading>
        <p>{description}</p>
      </div>
    </div>
  );
}

export default function HomepageFeatures(): ReactNode {
  return (
    <section className={styles.features}>
      <div className="container">
        <div className="row">
          {FeatureList.map((props, idx) => (
            <Feature key={idx} {...props} />
          ))}
        </div>
      </div>
    </section>
  );
}
