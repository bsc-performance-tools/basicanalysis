import React from 'react';

/** Keeps an error inside one panel from blanking the whole window. */
export default class PanelBoundary extends React.Component {
  constructor(props) {
    super(props);
    this.state = { error: null };
  }

  static getDerivedStateFromError(error) {
    return { error };
  }

  componentDidCatch(error) {
    console.error('Panel error:', error);
  }

  render() {
    if (this.state.error) {
      return (
        <div className="panel muted">
          <p>This panel could not be shown: {String(this.state.error.message || this.state.error)}</p>
          <button type="button" onClick={() => this.setState({ error: null })}>Try again</button>
        </div>
      );
    }
    return this.props.children;
  }
}
