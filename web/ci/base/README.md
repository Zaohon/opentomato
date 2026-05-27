# Shanghai Base Images

The Shanghai pipeline now builds `Dockerfile.shanghai` directly from
`docker.m.daocloud.io/library/nginx:1.27-alpine` via Kaniko.

The old rootfs-archive workflow was removed because carrying large tarballs in Git
made `get_sources` slow and unstable on the ACK runner.
