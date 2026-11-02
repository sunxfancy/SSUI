const { config, profileFromName } = require('./runtime_target.cjs');
const { loadConfig, generateRequirements } = require('./dependency_config.cjs');

function main(argv) {
  let check = false;
  const names = [];
  for (let i = 0; i < argv.length; i++) {
    if (argv[i] === '--check') check = true;
    else if (argv[i] === '--target') {
      if (!argv[i + 1] || argv[i + 1].startsWith('--')) throw new Error('--target 缺少目标名称');
      names.push(profileFromName(argv[++i]).dependencyTarget);
    } else throw new Error(`未知参数: ${argv[i]}`);
  }
  const spec = loadConfig();
  for (const name of new Set(names.length ? names : config.profiles.map(p => p.dependencyTarget))) {
    console.log(`${check ? 'Checked' : 'Generated'}: ${generateRequirements(name, { check, spec })}`);
  }
}

if (require.main === module) {
  try { main(process.argv.slice(2)); }
  catch (error) { console.error(error.message); process.exitCode = 1; }
}

module.exports = { main };
