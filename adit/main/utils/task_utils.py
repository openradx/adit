from ..site import job_delay_funcs


def delay_job(job):
    job_delay_funcs[job.job_type](job.id)
