#!/usr/bin/env nextflow
nextflow.enable.dsl=2

/*
 * TRANSFER
 *
 * Copies input files to an external output directory via publishDir.
 *
 * Notes:
 * - Input files are already staged into the task work directory by Nextflow.
 * - No explicit cp command is required.
 * - publishDir handles the actual export/copy operation.
 */
process TRANSFER {
  tag "${file_in}"
  publishDir params.transfer_outdir, mode: 'copy'

  input:
    path file_in

  output:
    path file_in

  script:
    """
    true
    """
}

process VALIDATE {
  tag "${file}"
  // Temp test. TODO: output them in a log directory on codon:
  publishDir params.transfer_outdir, mode: 'copy'

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
