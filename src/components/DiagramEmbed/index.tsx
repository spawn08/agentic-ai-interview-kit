import type {ReactNode} from 'react';
import useBaseUrl from '@docusaurus/useBaseUrl';
import styles from './styles.module.css';

type DiagramEmbedProps = {
  src: string;
  title: string;
  children: ReactNode;
};

export default function DiagramEmbed({src, title, children}: DiagramEmbedProps): ReactNode {
  const url = useBaseUrl(src);
  return (
    <figure className={styles.diagram}>
      <iframe
        className={styles.viewer}
        src={url}
        title={title}
        loading="lazy"
        allowFullScreen
      />
      <figcaption>
        {children}{' '}
        <a href={url} target="_blank" rel="noopener noreferrer">
          Open full-size diagram and export
        </a>.
      </figcaption>
    </figure>
  );
}
