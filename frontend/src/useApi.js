import { useEffect, useState } from "react";

// Runs `load` whenever `deps` change and tracks loading / error / data.
// Responses that arrive after the deps changed again are ignored.
export function useApi(load, deps) {
  const [state, setState] = useState({ data: null, error: null, loading: true });

  useEffect(() => {
    let current = true;
    setState((previous) => ({ ...previous, loading: true, error: null }));
    load()
      .then((data) => current && setState({ data, error: null, loading: false }))
      .catch((error) => current && setState({ data: null, error, loading: false }));
    return () => {
      current = false;
    };
  }, deps);

  return state;
}
