const fs = require('fs');
const path = require('path');

let count = 0;

const dir = process.argv[2] || '.';

function walk(dirPath) {
  fs.readdirSync(dirPath, { withFileTypes: true }).forEach((dirent) => {
    const fullPath = path.join(dirPath, dirent.name);

    if (dirent.name === 'node_modules' || dirent.name.startsWith('.')) {
      return;
    }

    try {
      fs.watch(fullPath, { persistent: false }, () => {});
      count += 1;
    } catch (err) {
      if (err.code === 'EMFILE') {
        console.error('EMFILE encountered at', fullPath, 'after', count, 'watchers');
        throw err;
      }
      console.warn('Failed to watch', fullPath, err.message);
    }

    if (dirent.isDirectory()) {
      walk(fullPath);
    }
  });
}

walk(dir);

console.log('watchers created:', count);
