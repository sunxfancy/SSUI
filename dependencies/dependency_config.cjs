const fs = require('node:fs');
const path = require('node:path');
const yaml = require('js-yaml');
const { config: targets, runtimeTarget, profileFromName, targetName } = require('./runtime_target.cjs');

const CONFIG_PATH = path.join(__dirname, 'dependencies.yaml');
const DIMENSIONS = { os: targets.oses, arch: targets.architectures, backend: targets.backends };
const canonicalName = name => name.split('[')[0].toLowerCase().replace(/[-_.]+/g, '-');

function object(value, label) {
  if (!value || typeof value !== 'object' || Array.isArray(value)) throw new Error(`${label} 必须是对象`);
}

function keys(value, allowed, label) {
  object(value, label);
  for (const key of Object.keys(value)) {
    if (!allowed.includes(key)) throw new Error(`${label}: 未知字段 ${key}`);
  }
}

function validateLayer(layer, label, conditional = false) {
  keys(layer, ['packages', 'extraIndexes', ...(conditional ? ['when'] : [])], label);
  if (layer.packages !== undefined) {
    object(layer.packages, `${label}.packages`);
    const seen = new Set();
    for (const [name, constraint] of Object.entries(layer.packages)) {
      if (!/^[A-Za-z0-9][A-Za-z0-9._-]*(?:\[[A-Za-z0-9,._-]+\])?$/.test(name)) throw new Error(`无效包名: ${name}`);
      const canonical = canonicalName(name);
      if (seen.has(canonical)) throw new Error(`${label}: 重复包名 ${name}`);
      seen.add(canonical);
      if (constraint === null) continue;
      const values = Array.isArray(constraint) ? constraint : [constraint];
      if (!values.length || values.some(v => typeof v !== 'string' || /[\r\n]/.test(v)
          || (v !== '' && !/^(?:[<>=!~]|@\s+https?:\/\/)/.test(v)))) {
        throw new Error(`${label}: ${name} 的约束无效`);
      }
    }
  }
  if (layer.extraIndexes !== undefined && (!Array.isArray(layer.extraIndexes)
      || layer.extraIndexes.some(url => typeof url !== 'string' || !/^https?:\/\/\S+$/.test(url)))) {
    throw new Error(`${label}.extraIndexes 必须是 HTTP(S) URL 数组`);
  }
  if (conditional) {
    keys(layer.when, Object.keys(DIMENSIONS), `${label}.when`);
    if (!Object.keys(layer.when).length) throw new Error(`${label}.when 不能为空`);
    for (const [dimension, selection] of Object.entries(layer.when)) {
      const values = Array.isArray(selection) ? selection : [selection];
      if (!values.length || values.some(v => !DIMENSIONS[dimension].includes(v))) {
        throw new Error(`${label}.when: 无效的 ${dimension}`);
      }
    }
  }
}

function validateConfig(spec) {
  keys(spec, ['version', 'common', 'os', 'arch', 'backend', 'overrides'], 'dependencies');
  if (spec.version !== 1) throw new Error('不支持的依赖配置版本');
  validateLayer(spec.common, 'common');
  for (const [dimension, values] of Object.entries(DIMENSIONS)) {
    keys(spec[dimension], values, dimension);
    for (const [name, layer] of Object.entries(spec[dimension])) validateLayer(layer, `${dimension}.${name}`);
  }
  if (!Array.isArray(spec.overrides)) throw new Error('overrides 必须是数组');
  spec.overrides.forEach((layer, i) => validateLayer(layer, `overrides[${i}]`, true));
  return spec;
}

function loadConfig(filename = CONFIG_PATH) {
  return validateConfig(yaml.load(fs.readFileSync(filename, 'utf8')));
}

function resolveDependencies(target, spec = loadConfig()) {
  const normalized = runtimeTarget(target.os, target.arch, target.backend);
  validateConfig(spec);
  const packages = new Map();
  const extraIndexes = new Set();
  const apply = layer => {
    for (const [name, value] of Object.entries(layer.packages || {})) {
      const canonical = canonicalName(name);
      if (value === null) packages.delete(canonical);
      else packages.set(canonical, { name, constraints: Array.isArray(value) ? value : [value] });
    }
    for (const url of layer.extraIndexes || []) extraIndexes.add(url);
  };
  apply(spec.common);
  for (const dimension of Object.keys(DIMENSIONS)) {
    const layer = spec[dimension][normalized[dimension]];
    if (!layer) throw new Error(`尚未声明依赖层 ${dimension}.${normalized[dimension]}`);
    apply(layer);
  }
  for (const layer of spec.overrides) {
    if (Object.entries(layer.when).every(([dimension, selection]) =>
      (Array.isArray(selection) ? selection : [selection]).includes(normalized[dimension]))) apply(layer);
  }
  const requirements = [...packages.entries()].sort(([a], [b]) => a.localeCompare(b, 'en'))
    .flatMap(([, { name, constraints }]) => constraints.map(c => `${name}${c.startsWith('@') ? ' ' : ''}${c}`));
  return { target: normalized, requirements, extraIndexes: [...extraIndexes] };
}

function renderRequirements(target, spec = loadConfig()) {
  const resolved = resolveDependencies(target, spec);
  return `# Generated from dependencies/dependencies.yaml. DO NOT EDIT.\n`
    + `# Target: ${targetName(resolved.target)}\n# Regenerate: yarn requirements:generate\n`
    + [...resolved.requirements, ...resolved.extraIndexes.map(url => `--extra-index-url ${url}`)].join('\n') + '\n';
}

function generateRequirements(name, { check = false, spec = loadConfig() } = {}) {
  const profile = profileFromName(name);
  const filename = path.join(__dirname, `requirements-${profile.dependencyTarget}.txt`);
  const content = renderRequirements(profile, spec);
  if (check) {
    if (!fs.existsSync(filename) || fs.readFileSync(filename, 'utf8').replace(/\r\n/g, '\n') !== content) {
      throw new Error(`生成文件已过期: ${filename}，请运行 yarn requirements:generate`);
    }
  } else fs.writeFileSync(filename, content);
  return filename;
}

module.exports = { CONFIG_PATH, canonicalName, validateConfig, loadConfig, resolveDependencies, renderRequirements, generateRequirements };
