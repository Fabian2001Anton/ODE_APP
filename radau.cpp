#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <math.h>
#include <float.h>
#include <ctype.h>
#include <sys/stat.h>

//Radau algorithm with s=3 (Order 5)
//We want to find the solution of the internal value problem 
// y'(t) = f(t,y(t)) (eq:1)
// with y(t0) = y0 and with f:R x R^d -> R^d

//equation 1 right hand side

typedef void (*radau_rhs)(double t, const double *y, double *dydt, void *par);

//Jacobi Matrix

typedef void (*radau_jac)(double t, const double *y, double *M_Jacobi, void *par);

//Iteration
//$$Y_i = y_n + h \sum_{j=1}^{s} a_{ij}\, f\big(t_n + c_j h,\; Y_j\big), \qquad i = 1, \dots, s,$$
//$$y_{n+1} = y_n + h \sum_{j=1}^{s} b_j\, f\big(t_n + c_j h,\; Y_j\big).$$
//with
//stepsize h

//Butcher-Tableau
//matrix a
static const double radau_A[3][3] = {
    { 0.19681547722366042587, -0.065535425850198388109,  0.02377097434822015242  },
    { 0.39442431473908727700,  0.29207341166522846302,  -0.041548752125997930198 },
    { 0.37640306270046727505,  0.51248582618842161384,   0.11111111111111111111  }
};
//vector b last line of A
//vector c
static const double radau_c[3] = {
    0.15505102572168219018, 0.64494897427831780982, 1.0
};

//memory 
 
typedef struct {
    int     d;          /* dimension of the ODE system           */
    int     n;          /* 3*d, size of the Newton system        */
    double *M_Jacobi;   /* d*d    Jacobi matrix                  */
    double *M_Newton;   /* n*n    I - h (A kron J), LU-decomposed */
    int    *piv;        /* n      pivot indices                  */
    double *Z;          /* n      stage increments Z_1..Z_3      */
    double *F;          /* n      f at the stages                */
    double *R;          /* n      residual / Newton correction   */
    double *ytmp;       /* d      temporary y                    */
    double *f0;         /* d      f(t_n, y_n) for FD Jacobi      */
    double *f1;         /* d      temporary f for FD Jacobi      */
} radau3_ws;
 
 
static int ws_alloc(radau3_ws *w, int d)
{
    w->d = d;
    w->n = 3 * d;
    w->M_Jacobi   = (double *)malloc(sizeof(double) * d * d);
    w->M_Newton   = (double *)malloc(sizeof(double) * w->n * w->n);
    w->piv = (int *)malloc(sizeof(int)    * w->n);
    w->Z   = (double *)malloc(sizeof(double) * w->n);
    w->F   = (double *)malloc(sizeof(double) * w->n);
    w->R   = (double *)malloc(sizeof(double) * w->n);
    w->ytmp  = (double *)malloc(sizeof(double) * d);
    w->f0  = (double *)malloc(sizeof(double) * d);
    w->f1  = (double *)malloc(sizeof(double) * d);
    return (w->M_Jacobi && w->M_Newton && w->piv && w->Z && w->F && w->R && w->ytmp && w->f0 && w->f1) ? 0 : -1;
}
 
static void ws_free(radau3_ws *w)
{free(w->M_Jacobi); free(w->M_Newton); free(w->piv); free(w->Z); free(w->F); free(w->R); free(w->ytmp); free(w->f0); free(w->f1);}

static int radau_step(radau_rhs f, radau3_ws *w, void *par, double t, double h, const double *y,double *ynew,
                      double abstol, double reltol)
    {  
        //d is the dimention of the ODE systhem
        const int d = w->d;          // dimension of the ODE system
        const int n = w->n;          // 3*d
        double *M_Jacobi = w->M_Jacobi;
        double *M_Newton = w->M_Newton;
        int    *piv      = w->piv;
        double *Z        = w->Z;
        double *F        = w->F;
        double *R        = w->R;
        double *ytmp     = w->ytmp;
        double *f0       = w->f0;
        double *f1       = w->f1;

        //Jaccobi Matrix
        //$Z_i = Y_i - y_n$ due to numerical issues
        //$$Z_i = h \sum_{j=1}^{3} a_{ij}\, f(t + c_j h,\; y_n + Z_j), \qquad i = 1, 2, 3.$$      
            f(t, y, f0, par);
            memcpy(ytmp, y, sizeof(double) * d);
            for (int j = 0; j < d; j++) {
                double delta = sqrt(DBL_EPSILON) * fmax(1e-5, fabs(y[j]));
                ytmp[j] = y[j] + delta;
                f(t, ytmp, f1, par);
                for (int i = 0; i < d; i++) M_Jacobi[i * d + j] = (f1[i] - f0[i]) / delta; 
            ytmp[j] = y[j];
            }

        //Newton matrix M_Newton of the size n = 3d
        //$$M = I_{3d} - h\,(A \otimes J) = \begin{pmatrix} I - h a_{11} J & -h a_{12} J & -h a_{13} J \\ -h a_{21} J & I - h a_{22} J & -h a_{23} J \\ -h a_{31} J & -h a_{32} J & I - h a_{33} J \end{pmatrix}.$$
            for (int i = 0; i < 3; i++)
            for (int j = 0; j < 3; j++)
            for (int k = 0; k < d; k++)
            for (int l = 0; l < d; l++)
                w->M_Newton[(i * d + k) * n + (j * d + l)]
                = ((i == j && k == l) ? 1.0 : 0.0) - h * radau_A[i][j] * M_Jacobi[k * d + l];

        //lu decomposition with piovot strategy
            for (int k = 0; k < n; k++) {
                int p = k;
                double maxv = fabs(M_Newton[k * n + k]);
                for (int i = k + 1; i < n; i++) {
                    double v = fabs(M_Newton[i * n + k]);
                    if (v > maxv) { maxv = v; p = i; }
                }
                if (maxv == 0.0) return 2;
                piv[k] = p;
                if (p != k)
                    for (int j = 0; j < n; j++) {
                        double tmp = M_Newton[k * n + j];
                        M_Newton[k * n + j] = M_Newton[p * n + j];
                        M_Newton[p * n + j] = tmp;
                    }
                double pivot = M_Newton[k * n + k];
                for (int i = k + 1; i < n; i++) {
                    double l = (M_Newton[i * n + k] /= pivot);
                    if (l != 0.0)
                        for (int j = k + 1; j < n; j++)
                            M_Newton[i * n + j] -= l * M_Newton[k * n + j];
                }
            }

        //starting value
            memset(Z, 0, sizeof(double) * n);
        
        //Newton iteration
            double prev = HUGE_VAL;

            for (int it = 0; it < 10; it++) {
                for (int i = 0; i < 3; i++) {
                    for (int k = 0; k < d; k++) ytmp[k] = y[k] + Z[i * d + k];
                    f(t + radau_c[i] * h, ytmp, F + i * d, par);
                }
                //calculate the residual
                    for (int i = 0; i < 3; i++)
                        for (int k = 0; k < d; k++) {
                            double s = 0.0;
                            for (int j = 0; j < 3; j++) s += radau_A[i][j] * F[j * d + k];
                            w->R[i * d + k] = -Z[i * d + k] + h * s;
                    }
                //Newton step for $$G(Z) = Z - h\,(A \otimes I_d)\, F(Z), 
                //\qquad F(Z) = \begin{pmatrix} f(t + c_1 h, y_n + Z_1) \\ f(t + c_2 h, y_n + Z_2) \\ f(t + c_3 h, y_n + Z_3) \end{pmatrix}$$
                    //double *M_Newton;
                    //redidual R
                    for (int k = 0; k < n; k++)
                        if (piv[k] != k) { double tmp = R[k]; R[k] = R[piv[k]]; R[piv[k]] = tmp; }
                    for (int i = 1; i < n; i++)
                        for (int j = 0; j < i; j++)
                            R[i] -= M_Newton[i * n + j] * R[j];
                    for (int i = n - 1; i >= 0; i--) {
                        for (int j = i + 1; j < n; j++)
                            R[i] -= M_Newton[i * n + j] * R[j];
                        R[i] /= M_Newton[i * n + i];
                    }
                //calculate the RMS-Norm with weights
                //$$\|\Delta Z\| = \sqrt{\frac{1}{3d} \sum_{i,k} \left( \frac{\Delta Z_{i,k}}{\text{atol} + \text{rtol}\,|y_{n,k}|} \right)^2}$$
                    double nrm = 0.0;
                    for (int i = 0; i < 3; i++)
                        for (int k = 0; k < d; k++) {
                            double dz = R[i * d + k];
                            Z[i * d + k] += dz;
                            double sc = abstol + reltol * fabs(y[k]);
                            nrm += (dz / sc) * (dz / sc);
                        }
                    nrm = sqrt(nrm / n);
                //tests:
                    if (!isfinite(nrm)) return 1;
                    if (nrm <= 1.0) {
                            for (int k = 0; k < d; k++) ynew[k] = y[k] + Z[2 * d + k];
                            return 0;
                        }
                if (it > 0 && nrm > 2.0 * prev) return 1;
                prev = nrm;   
            }
    return 1;
}

// ---------------- system from the JSON file ----------------

#define MAXD 64

static int    d, np; //d number of equations
static char  *eq[MAXD];
static char   pname[MAXD][32];
static double pval[MAXD];  //parameter values

static const char   *ep; // current position in the formula
static double ev_t;
static const double *ev_y;

static const struct { const char *n; double (*f)(double); } fns[] = {
    {"sin", sin},   {"cos", cos},   {"tan", tan},   {"asin", asin}, {"acos", acos},
    {"atan", atan}, {"sinh", sinh}, {"cosh", cosh}, {"tanh", tanh}, {"exp", exp},
    {"log", log},   {"log10", log10}, {"sqrt", sqrt} };

static double sum(void);
static double unary(void);
static void   ws(void) { while (isspace((unsigned char)*ep)) ep++; } //handle whitespace

//prim is short for primary, smallers componount of the equations
static double prim(void)
{
    ws();
    if (*ep == '(') { ep++; double v = sum(); ws(); ep++; return v; } //handles brackets
    if (isdigit((unsigned char)*ep) || *ep == '.') return strtod(ep, (char **)&ep); //handles numbers
    //now names
        char n[32]; int k = 0;
        while (isalnum((unsigned char)*ep) || *ep == '_') n[k++] = *ep++;
        n[k] = '\0'; ws();
        //functions
            if (*ep == '(') {
                ep++; double a = sum(); ws(); ep++;
                for (size_t i = 0; i < sizeof fns / sizeof fns[0]; i++)
                    if (!strcmp(n, fns[i].n)) return fns[i].f(a);
            }
        //time and constants
            if (!strcmp(n, "t"))  return ev_t;
            if (!strcmp(n, "pi")) return 3.14159265358979323846;
            if (!strcmp(n, "e"))  return 2.71828182845904523536;
        if (n[0] == 'y' && isdigit((unsigned char)n[1])) return ev_y[atoi(n + 1) - 1]; //variable
        //prameter will be replaced with the correct value
        for (int i = 0; i < np; i++) if (!strcmp(n, pname[i])) return pval[i]; 
    return NAN;
}

//power function
static double power(void)
{
    double b = prim(); ws();
    if (*ep == '^')                  { ep += 1; return pow(b, unary()); }
    if (ep[0] == '*' && ep[1] == '*') { ep += 2; return pow(b, unary()); }
    return b;
}
//handle minus signs
static double unary(void) { ws(); if (*ep == '-') { ep++; return -unary(); } return power(); }

//handles products and divisions of differnt sizes
static double prod(void)
{
    double v = unary();
    for (;;) { ws();
        if      (*ep == '*') { ep++; v *= unary(); }
        else if (*ep == '/') { ep++; v /= unary(); }
        else return v; }
}

//handles addition and subtraction
static double sum(void)
{
    double v = prod();
    for (;;) { ws();
        if      (*ep == '+') { ep++; v += prod(); }
        else if (*ep == '-') { ep++; v -= prod(); }
        else return v; }
}

//help function for the RHS
static void rhs(double t, const double *y, double *dydt, void *par)
{
    (void)par;
    ev_t = t; ev_y = y;
    for (int i = 0; i < d; i++) { ep = eq[i]; dydt[i] = sum(); }
}

//points to vlues in the JSON file
static char *key(char *s, const char *k)
{
    char q[64]; snprintf(q, sizeof q, "\"%s\"", k);
    s = strstr(s, q);
    return s ? strchr(s + strlen(q), ':') + 1 : NULL;
}

//writes a line to the CSV
static void row(FILE *out, double t, const double *y)
{
    fprintf(out, "\n%.17g", t);
    for (int i = 0; i < d; i++) fprintf(out, ",%.17g", y[i]);
}
 
// skip whitespace and commas
static char *skip(char *s) { while (isspace((unsigned char)*s) || *s == ',') s++; return s; }


int main(int argc, char **argv) {
    // read file
    char path[512];
    snprintf(path, sizeof path, "Models/%s", argc > 1 ? argv[1] : "system.json");
    FILE *fp = fopen(path, "rb"); //reads in binary mode
    if (!fp) return 1;
    fseek(fp, 0, SEEK_END); long len = ftell(fp); rewind(fp); //getting file size
    //save in memory and close file
    char *text = (char *)malloc(len + 1);
    text[fread(text, 1, len, fp)] = '\0';
    fclose(fp);
 
    double t0 = strtod(key(text, "t_start"), NULL);
    double t1 = strtod(key(text, "t_end"),   NULL);

    char *s, *e;
    //parameters
    if ((s = key(text, "parameters")))
    for (s = strchr(s, '{') + 1; *(s = skip(s)) != '}'; np++) {
        e = strchr(s + 1, '"');
        snprintf(pname[np], 32, "%.*s", (int)(e - s - 1), s + 1);
        pval[np] = strtod(strchr(e, ':') + 1, &s);
    }
    //initial values
    double y[MAXD], ynew[MAXD];
    s = strchr(key(text, "y0"), '[') + 1;
    for (int i = 0; *(s = skip(s)) != ']'; i++) y[i] = strtod(s, &s);
    //step size 1/1000 length
    double h = (s = key(text, "h")) ? strtod(s, NULL) : (t1 - t0) / 1000.0;
    //equations
    for (s = strchr(key(text, "equations"), '[') + 1; *(s = skip(s)) != ']'; s = e + 1) {
        e = strchr(s + 1, '"');
        *e = '\0';
        eq[d++] = s + 1;
    }
    //prepare output
    mkdir("solutions", 0755);
    snprintf(path, sizeof path, "solutions/%s", argc > 2 ? argv[2] : "solution.csv");
    FILE *out = fopen(path, "w");
    fprintf(out, "t");
    for (int i = 0; i < d; i++) fprintf(out, ",y%d", i + 1);

    //prepare solver
    radau3_ws w;
    ws_alloc(&w, d);
    double t = t0;
    row(out, t, y);

    //TIME LOOP
    while (t < t1) {
        int last = (t + h >= t1);
        double hh = last ? t1 - t : h;
        if (radau_step(rhs, &w, NULL, t, hh, y, ynew, 1e-10, 1e-10) != 0) {
            h /= 2;                                   // Newton failed: retry smaller
            if (h < 1e-14 * (t1 - t0)) break;
            continue;
        }
        memcpy(y, ynew, sizeof(double) * d);
        t = last ? t1 : t + hh;
        row(out, t, y);
    }

    //clean up 
    fprintf(out, "\n");
    fclose(out);
    ws_free(&w);
    free(text);

    return 0;}