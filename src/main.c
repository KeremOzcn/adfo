#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <time.h>
#include "../include/warehouse.h"
#include "../include/instances.h"
#include "../include/baselines.h"
#include "../include/depso.h"
#include "../include/rbrs_ae_algorithm.h"

#define N_SEEDS      3
#define CAP_OVERRIDE 5.0   /* tight capacity to force meaningful batching */

static const int SEEDS[N_SEEDS] = {42, 43, 44};

typedef struct {
    int    seed;
    double sop, fcfs, depso, depso_time_s, rbrs, rbrs_time_s;
} RunResult;

static double elapsed(clock_t start) {
    return (double)(clock() - start) / CLOCKS_PER_SEC;
}

static void write_csv(const char *path, const char *sid,
                      const RunResult *rows, int n) {
    FILE *f = fopen(path, "w");
    if (!f) { fprintf(stderr, "Cannot open %s\n", path); return; }
    fprintf(f, "scenario_id,seed,sop_distance,fcfs_distance,"
               "depso_distance,depso_time_s,"
               "rbrs_distance,rbrs_time_s,"
               "rbrs_vs_depso_pct,depso_vs_sop_pct,rbrs_vs_sop_pct\n");
    for (int i = 0; i < n; i++) {
        double rdp = rows[i].depso > 0
            ? (rows[i].depso - rows[i].rbrs)  / rows[i].depso * 100.0 : 0.0;
        double dsp = rows[i].sop > 0
            ? (rows[i].sop   - rows[i].depso) / rows[i].sop   * 100.0 : 0.0;
        double rsp = rows[i].sop > 0
            ? (rows[i].sop   - rows[i].rbrs)  / rows[i].sop   * 100.0 : 0.0;
        fprintf(f, "%s,%d,%.1f,%.1f,%.1f,%.3f,%.1f,%.3f,%.4f,%.4f,%.4f\n",
                sid, rows[i].seed,
                rows[i].sop, rows[i].fcfs,
                rows[i].depso, rows[i].depso_time_s,
                rows[i].rbrs,  rows[i].rbrs_time_s,
                rdp, dsp, rsp);
    }
    fclose(f);
}

static void write_summary_json(const char *path, const char *sid,
                                const RunResult *rows, int n) {
    double sop_s=0, fcfs_s=0, dep_s=0, rbs_s=0;
    double dep_sq=0, rbs_sq=0;
    double dep_mn=1e18, dep_mx=-1e18, rbs_mn=1e18, rbs_mx=-1e18;
    for (int i = 0; i < n; i++) {
        sop_s += rows[i].sop; fcfs_s += rows[i].fcfs;
        dep_s += rows[i].depso; rbs_s += rows[i].rbrs;
        dep_sq += rows[i].depso * rows[i].depso;
        rbs_sq += rows[i].rbrs  * rows[i].rbrs;
        if (rows[i].depso < dep_mn) dep_mn = rows[i].depso;
        if (rows[i].depso > dep_mx) dep_mx = rows[i].depso;
        if (rows[i].rbrs  < rbs_mn) rbs_mn = rows[i].rbrs;
        if (rows[i].rbrs  > rbs_mx) rbs_mx = rows[i].rbrs;
    }
    double dm = dep_s/n, rm = rbs_s/n, sm = sop_s/n, fm = fcfs_s/n;
    double ds = n>1 ? sqrt(dep_sq/n - dm*dm) : 0.0;
    double rs = n>1 ? sqrt(rbs_sq/n - rm*rm) : 0.0;

    FILE *f = fopen(path, "w");
    if (!f) { fprintf(stderr, "Cannot open %s\n", path); return; }
    fprintf(f,
        "{\n"
        "  \"scenario_id\": \"%s\",\n"
        "  \"n_instances\": %d,\n"
        "  \"sop_mean\": %.2f,\n"
        "  \"fcfs_mean\": %.2f,\n"
        "  \"depso_mean\": %.2f,\n"
        "  \"depso_std\": %.2f,\n"
        "  \"depso_min\": %.1f,\n"
        "  \"depso_max\": %.1f,\n"
        "  \"rbrs_mean\": %.2f,\n"
        "  \"rbrs_std\": %.2f,\n"
        "  \"rbrs_min\": %.1f,\n"
        "  \"rbrs_max\": %.1f,\n"
        "  \"rbrs_vs_depso_mean_pct\": %.4f,\n"
        "  \"depso_vs_sop_mean_pct\": %.4f,\n"
        "  \"rbrs_vs_sop_mean_pct\": %.4f\n"
        "}",
        sid, n, sm, fm,
        dm, ds, dep_mn, dep_mx,
        rm, rs, rbs_mn, rbs_mx,
        dm>0 ? (dm-rm)/dm*100.0 : 0.0,
        sm>0 ? (sm-dm)/sm*100.0 : 0.0,
        sm>0 ? (sm-rm)/sm*100.0 : 0.0);
    fclose(f);
}

int main(void) {
    printf("=== Order Batching Benchmark ===\n\n");
    system("mkdir -p results");

    WarehouseConfig wcfg = {10, 4, 45, 2.0, 1.0, 2.0, 1.0};
    Warehouse *wh = warehouse_create(&wcfg);
    if (!wh) { fprintf(stderr, "warehouse_create failed\n"); return 1; }

    Scenario scenarios[] = { {50, 6, 6}, {100, 6, 6} };
    int n_sc = (int)(sizeof(scenarios) / sizeof(scenarios[0]));

    char *summary_bufs[8]; int n_sum = 0;

    for (int si = 0; si < n_sc; si++) {
        Scenario *sc = &scenarios[si];
        char sid[64];
        snprintf(sid, sizeof(sid), "%d_%d_%d",
                 sc->n_orders, sc->n_max_orderlines, sc->a_max_per_line);

        printf("Scenario: %s  (cap=%.0f wu, %d seeds)\n",
               sid, CAP_OVERRIDE, N_SEEDS);
        printf("%-6s %8s %8s %10s %10s\n",
               "seed", "SOP", "FCFS", "DEPSO", "RBRS-AE");
        printf("------------------------------------------\n");

        RunResult rows[N_SEEDS];

        for (int ki = 0; ki < N_SEEDS; ki++) {
            Instance *inst = generate_instance(sc, wh, SEEDS[ki]);
            if (!inst) continue;
            inst->vehicle_capacity_wu = CAP_OVERRIDE;
            rows[ki].seed = SEEDS[ki];
            rows[ki].sop  = sop_distance(inst, wh);
            rows[ki].fcfs = fcfs_distance(inst, wh);

            DEPSOConfig dcfg = {5, 200, 0.5, 0.3, 50, 20};
            DEPSO *d = depso_create(inst, wh, &dcfg, (unsigned)SEEDS[ki]);
            clock_t t0 = clock();
            rows[ki].depso = depso_run(d, NULL, NULL);
            rows[ki].depso_time_s = elapsed(t0);
            depso_destroy(d);

            RBRS_AE *r = rbrs_create(inst, wh, 100, 20);
            t0 = clock();
            rows[ki].rbrs = rbrs_run(r, NULL, NULL);
            rows[ki].rbrs_time_s = elapsed(t0);
            rbrs_destroy(r);

            printf("%-6d %8.0f %8.0f %10.0f %10.0f\n",
                   SEEDS[ki], rows[ki].sop, rows[ki].fcfs,
                   rows[ki].depso, rows[ki].rbrs);
            destroy_instance(inst);
        }

        double sm=0, fm=0, dm=0, rm=0;
        for (int i=0; i<N_SEEDS; i++) {
            sm+=rows[i].sop; fm+=rows[i].fcfs;
            dm+=rows[i].depso; rm+=rows[i].rbrs;
        }
        sm/=N_SEEDS; fm/=N_SEEDS; dm/=N_SEEDS; rm/=N_SEEDS;
        printf("\nAvg vs SOP:  FCFS %+.1f%%  DEPSO %+.1f%%  RBRS-AE %+.1f%%\n\n",
               (fm-sm)/sm*100.0, (dm-sm)/sm*100.0, (rm-sm)/sm*100.0);

        char csv[256], jsn[256];
        snprintf(csv, sizeof(csv), "results/benchmark_results_%s.csv", sid);
        snprintf(jsn, sizeof(jsn), "results/summary_%s.json", sid);
        write_csv(csv, sid, rows, N_SEEDS);
        write_summary_json(jsn, sid, rows, N_SEEDS);
        printf("  Wrote %s\n  Wrote %s\n\n", csv, jsn);

        /* Buffer JSON for summary_full.json */
        FILE *jf = fopen(jsn, "r");
        if (jf) {
            fseek(jf, 0, SEEK_END); long sz = ftell(jf); rewind(jf);
            char *buf = malloc(sz + 2);
            if (buf) { fread(buf, 1, sz, jf); buf[sz]='\0'; summary_bufs[n_sum++]=buf; }
            fclose(jf);
        }
    }

    /* Write summary_full.json as JSON array */
    FILE *sf = fopen("results/summary_full.json", "w");
    if (sf) {
        fprintf(sf, "[\n");
        for (int i = 0; i < n_sum; i++) {
            char *p = summary_bufs[i];
            /* indent by 2 spaces */
            int at_start = 1;
            for (; *p; p++) {
                if (at_start) { fprintf(sf, "  "); at_start=0; }
                fputc(*p, sf);
                if (*p == '\n') at_start = 1;
            }
            fprintf(sf, i < n_sum-1 ? ",\n" : "\n");
            free(summary_bufs[i]);
        }
        fprintf(sf, "]\n");
        fclose(sf);
        printf("Wrote results/summary_full.json\n");
    }

    warehouse_destroy(wh);
    return 0;
}
