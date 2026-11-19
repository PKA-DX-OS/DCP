# SPDX-FileCopyrightText: 2026 DX-OS Open-Core contributors
# SPDX-License-Identifier: AGPL-3.0-or-later

FROM postgrest/postgrest:v12.2.8
COPY --from=busybox:musl /bin/sh /bin/sh
COPY --from=busybox:musl /bin/wget /bin/wget
COPY --from=busybox:musl /bin/busybox /bin/busybox
