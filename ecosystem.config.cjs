module.exports = {
  apps: [
    {
      name: "garminsynapse",
      cwd: "/root/garminsynapse",
      script: "./run.sh",
      args: "-m garminsynapse.cli start-server --host 0.0.0.0 --port 6060",
      interpreter: "none",
      autorestart: true,
      restart_delay: 5000,
      exp_backoff_restart_delay: 2000,
      max_restarts: 15,
      min_uptime: "20s",
      kill_timeout: 5000,
      watch: false,
      max_memory_restart: "500M",
      env: {
        PYTHONUNBUFFERED: "1"
      }
    }
  ]
};
