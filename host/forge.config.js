module.exports = {
  packagerConfig: {
    asar: true,
    executableName: "flats-host",
    icon: "assets/brand/icon"
  },
  makers: [
    {
      name: "@electron-forge/maker-squirrel",
      config: {
        name: "flats_host",
        setupIcon: "assets/brand/icon.ico"
      }
    },
    {
      name: "@electron-forge/maker-zip",
      platforms: ["darwin"]
    },
    {
      name: "@electron-forge/maker-deb",
      config: {}
    }
  ]
};
