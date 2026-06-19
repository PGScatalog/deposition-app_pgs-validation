#!/usr/bin/env nextflow
nextflow.enable.dsl=2

/*
 * TRANSFER
 *
 * Copies input files to an external output directory via publishDir.
 *
 * Notes:
 * - file_in might not exist yet (waiting for the FTP transfer to complete), so we poll for it every 10min for up to 1 hour.
 * - a new transfer attempt is triggered if the file is still not found after 1 hour (exit code 75).
 * - the actual copy is done in the work directory so that Nextflow can stage and publish it.
 */
process TRANSFER {
  tag "${file_in}"
  publishDir "${params.submission_dir}/scores", mode: 'copy'

  errorStrategy { task.exitStatus == 75 ? 'retry' : 'terminate' }
  maxRetries 5

  input:
    val file_in  // val to avoid early staging

  output:
    path "./${file(file_in).name}"

  script:
    def filename = file(file_in).name
    """
    # Poll every 10min for up to 1 hour (6 attempts × 600s = 3600s)
    found=false
    for i in \$(seq 1 6); do
      if [ -f "${file_in}" ]; then
        found=true
        break
      fi
      echo "Attempt \$i: ${file_in} not found, waiting 60s..."
      sleep 600
    done

    # Exit code 75 triggers retry; other failures terminate
    if [ "\$found" = false ]; then
      echo "File not found after 1 hour"
      exit 75
    fi

    # Copy into work dir so Nextflow can stage/publish it
    cp "${file_in}" "./${filename}"
    """
}

process VALIDATE {
  tag "${file}"
  // Temp test. TODO: output them in a log directory on codon:
  publishDir "${params.submission_dir}/logs", mode: 'copy'

  input:
    path file

  output:
    path "${file.simpleName}.log"

  script:
    """
    export PYTHONPATH="${projectDir}/lib:\$PYTHONPATH"
    fname=\$(basename ${file})
    out="\${fname}.log"
    validate.py --input ${file} --output ${file.simpleName}.log
    """
}

process REPORT {
  tag "report"

  input:
    path validation_logs

  script:
    """
    echo ${validation_logs}
    report_mongo.py --logs ${validation_logs.join(' ')} --submission_id '${params.submission_id}' --mongoUri '${params.mongoUri}' --db '${params.mongoDb}'
    """
}

workflow {
  if( !params.scoring_file_names )
    error "You must provide --scoring_file_names"
  
  def files_ch
  def items = (params.scoring_file_names instanceof List) ? params.scoring_file_names : params.scoring_file_names.split(',').collect{ s -> s.trim() }
  //println(items)
  //def chans = items.collect { item -> Channel.fromPath("${params.input_dir}/${item}", checkIfExists: true) }
  //println(chans)
  files_ch = channel.fromPath(
    items.collect { item -> "${params.input_dir}/${params.submission_id}/${item}" }
  )
  //files_ch = Channel.merge(*chans)
  files_ch.view()

  transferred = TRANSFER(files_ch)
  println "Transferred files: ${transferred}"
  logs = VALIDATE(transferred).collect()
  REPORT(logs)
}
