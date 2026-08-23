module.exports = {
  apps: [
    {
      name: "garminsynapse",
      cwd: "/root/garminsynapse",
      script: "python3",
      args: "-m garminsynapse.cli start-server --host 0.0.0.0 --port 6060",
      interpreter: "none",
      autorestart: true,
      watch: false,
      max_memory_restart: "1G",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
