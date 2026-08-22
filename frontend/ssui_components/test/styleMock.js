// Jest mock for CSS module imports
module.exports = new Proxy(
    {},
    {
        get: (_target, prop) => prop,
    }
);
