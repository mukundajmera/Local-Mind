let iteration = 0;
const report = () => {
  iteration += 1;
  const handles = process._getActiveHandles();
  const watchers = handles.filter(
    (handle) => handle && handle.constructor && handle.constructor.name.includes('FSWatcher')
  );
  console.log(`[${iteration}] handles=${handles.length} watchers=${watchers.length}`);
};

setInterval(report, 2000);
